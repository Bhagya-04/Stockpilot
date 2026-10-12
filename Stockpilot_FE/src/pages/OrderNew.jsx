import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client.js';
import { Field } from '../components/FormField.jsx';
import { EmptyState, ErrorBanner, Loading } from '../components/States.jsx';
import { useConfirm } from '../context/ConfirmContext.jsx';
import { useCurrentWorkspace } from '../context/WorkspaceContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { useApi, useDebounce } from '../hooks/useApi.js';
import { formatCents, formatMoney, lineTotalCents } from '../utils/money.js';

const newKey = () =>
  globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;

export default function OrderNew() {
  const { workspaceId, can } = useCurrentWorkspace();
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();

  const [lines, setLines] = useState([]); // [{ product, quantity: '1' }]
  const [notes, setNotes] = useState('');
  const [search, setSearch] = useState('');
  const [error, setError] = useState(null);
  const [problems, setProblems] = useState({}); // product_id -> message from the server
  const [submitting, setSubmitting] = useState(false);

  // One idempotency key per distinct order payload: retrying the same form (e.g. after a network
  // drop) can never create two orders, while editing the order starts a new key.
  const keyRef = useRef(newKey());
  const touch = () => {
    keyRef.current = newKey();
    setError(null);
  };

  const debounced = useDebounce(search, 250);
  const results = useApi(
    () => api.products.list(workspaceId, { q: debounced, active: 'active', page_size: 8, sort_by: 'name', sort_dir: 'asc' }),
    [workspaceId, debounced],
  );

  if (!can('order:create')) {
    return (
      <div className="card center-card">
        <h1>Not allowed</h1>
        <p className="muted">Your role cannot create orders.</p>
      </div>
    );
  }

  const addProduct = (product) => {
    touch();
    setLines((current) => {
      const existing = current.find((l) => l.product.id === product.id);
      if (existing) {
        return current.map((l) =>
          l.product.id === product.id ? { ...l, product, quantity: String(Math.min(Number(l.quantity || 0) + 1, product.stock_quantity)) } : l,
        );
      }
      return [...current, { product, quantity: '1' }];
    });
  };

  const setQuantity = (id, quantity) => {
    touch();
    setLines((current) => current.map((l) => (l.product.id === id ? { ...l, quantity } : l)));
  };

  const removeLine = (id) => {
    touch();
    setLines((current) => current.filter((l) => l.product.id !== id));
  };

  const lineError = (line) => {
    const q = line.quantity.trim();
    if (!/^\d+$/.test(q) || Number(q) < 1) return 'Enter a whole number, 1 or more';
    if (Number(q) > line.product.stock_quantity) return `Only ${line.product.stock_quantity} in stock`;
    return null;
  };

  const totalCents = lines.reduce((sum, l) => sum + lineTotalCents(l.product.unit_price, /^\d+$/.test(l.quantity) ? Number(l.quantity) : 0), 0);
  const anyLineInvalid = lines.some(lineError);

  const submit = async (e) => {
    e.preventDefault();
    if (submitting || lines.length === 0 || anyLineInvalid) return;

    const ok = await confirm({
      title: 'Place this order?',
      message: (
        <>
          <p>
            {lines.length} {lines.length === 1 ? 'product' : 'products'}, estimated total <strong>{formatCents(totalCents)}</strong>.
          </p>
          <p className="muted">Stock for these items is reserved immediately. You can cancel the order later to release it.</p>
        </>
      ),
      confirmLabel: 'Place order',
    });
    if (!ok) return;

    setSubmitting(true);
    setError(null);
    setProblems({});
    try {
      const order = await api.orders.create(
        workspaceId,
        { items: lines.map((l) => ({ product_id: l.product.id, quantity: Number(l.quantity) })), notes: notes.trim() || null },
        keyRef.current,
      );
      toast.success(`Order ${order.display_number} placed`);
      navigate(`/w/${workspaceId}/orders/${order.id}`);
    } catch (err) {
      setError(err);
      const byProduct = {};
      for (const d of err.details || []) if (d.product_id) byProduct[d.product_id] = d.message;
      setProblems(byProduct);
      // Refresh what we know about stock so the user can correct quantities.
      setLines((current) =>
        current.map((l) => {
          const detail = (err.details || []).find((d) => d.product_id === l.product.id && d.available !== undefined);
          return detail ? { ...l, product: { ...l.product, stock_quantity: detail.available } } : l;
        }),
      );
      setSubmitting(false);
    }
  };

  return (
    <>
      <p>
        <Link to={`/w/${workspaceId}/orders`}>← Orders</Link>
      </p>
      <div className="page-header">
        <h1>New order</h1>
      </div>

      <div className="two-col order-builder">
        <section className="card">
          <h2>1. Add products</h2>
          <Field label="Search active products">
            {(a11y) => <input {...a11y} type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name or SKU" />}
          </Field>
          <ErrorBanner error={results.error} onRetry={results.refetch} />
          {results.loading && !results.data && <Loading label="Searching…" />}
          {results.data && results.data.items.length === 0 && <EmptyState title="No active products found" />}
          {results.data && results.data.items.length > 0 && (
            <ul className="picker">
              {results.data.items.map((p) => {
                const inOrder = lines.find((l) => l.product.id === p.id);
                const soldOut = p.stock_quantity === 0;
                return (
                  <li key={p.id}>
                    <div>
                      <strong>{p.name}</strong> <code>{p.sku}</code>
                      <div className="muted small">
                        {formatMoney(p.unit_price)} · {soldOut ? <span className="stock-low">Out of stock</span> : `${p.stock_quantity} in stock`}
                      </div>
                    </div>
                    <button type="button" className="btn btn-small" disabled={soldOut || (inOrder && Number(inOrder.quantity) >= p.stock_quantity)} onClick={() => addProduct(p)}>
                      {inOrder ? '＋1' : 'Add'}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="card">
          <h2>2. Review order</h2>
          <form onSubmit={submit} noValidate>
            <ErrorBanner error={error} />
            {lines.length === 0 ? (
              <EmptyState title="No products added yet">Search and add at least one product.</EmptyState>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th className="num">Price</th>
                      <th className="num">Qty</th>
                      <th className="num">Line total</th>
                      <th>
                        <span className="visually-hidden">Remove</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((l) => {
                      const err = lineError(l) || problems[l.product.id];
                      return (
                        <tr key={l.product.id}>
                          <td>
                            {l.product.name} <code>{l.product.sku}</code>
                            {err && <div className="field-error">{err}</div>}
                          </td>
                          <td className="num">{formatMoney(l.product.unit_price)}</td>
                          <td className="num">
                            <input
                              className="qty"
                              inputMode="numeric"
                              aria-label={`Quantity for ${l.product.name}`}
                              aria-invalid={err ? true : undefined}
                              value={l.quantity}
                              onChange={(e) => setQuantity(l.product.id, e.target.value)}
                            />
                          </td>
                          <td className="num">{formatCents(lineTotalCents(l.product.unit_price, /^\d+$/.test(l.quantity) ? Number(l.quantity) : 0))}</td>
                          <td>
                            <button type="button" className="btn btn-small btn-danger-outline" onClick={() => removeLine(l.product.id)} aria-label={`Remove ${l.product.name}`}>
                              ✕
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr>
                      <th colSpan={3} className="num">
                        Estimated total
                      </th>
                      <th className="num">{formatCents(totalCents)}</th>
                      <th />
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
            <p className="muted small">The final prices and total are calculated by the server when you place the order.</p>
            <Field label="Notes (optional)">
              {(a11y) => (
                <textarea
                  {...a11y}
                  rows={2}
                  maxLength={500}
                  value={notes}
                  onChange={(e) => {
                    touch();
                    setNotes(e.target.value);
                  }}
                />
              )}
            </Field>
            <div className="form-actions">
              <button className="btn btn-primary" disabled={submitting || lines.length === 0 || anyLineInvalid}>
                {submitting ? 'Placing order…' : 'Place order'}
              </button>
            </div>
          </form>
        </section>
      </div>
    </>
  );
}
