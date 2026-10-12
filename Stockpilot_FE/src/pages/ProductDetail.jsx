import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { InactiveBadge, LowStockBadge } from '../components/Badges.jsx';
import { Field, SelectField } from '../components/FormField.jsx';
import HistoryTable from '../components/HistoryTable.jsx';
import Pagination from '../components/Pagination.jsx';
import ProductForm from '../components/ProductForm.jsx';
import { EmptyState, ErrorBanner, Loading } from '../components/States.jsx';
import { useConfirm } from '../context/ConfirmContext.jsx';
import { useCurrentWorkspace } from '../context/WorkspaceContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { useApi } from '../hooks/useApi.js';
import { MANUAL_REASONS, PAGE_SIZE, REASON_LABELS } from '../utils/format.js';
import { formatMoney } from '../utils/money.js';

const REASON_HINT = {
  RECEIVED: 'Adds stock (enter a positive number).',
  RETURNED: 'Adds stock (enter a positive number).',
  DAMAGED: 'Removes stock (enter a negative number).',
  CORRECTION: 'Positive or negative, to match a physical count.',
  OTHER: 'Positive or negative. A note is required.',
};

function AdjustStock({ product, workspaceId, onDone }) {
  const confirm = useConfirm();
  const toast = useToast();
  const [form, setForm] = useState({ quantity_change: '', reason: 'RECEIVED', note: '' });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const change = Number(form.quantity_change);

  const validate = () => {
    const next = {};
    if (!/^[+-]?\d+$/.test(form.quantity_change.trim()) || change === 0) next.quantity_change = 'Enter a whole number other than 0 (e.g. 10 or -3)';
    else if (['RECEIVED', 'RETURNED'].includes(form.reason) && change < 0) next.quantity_change = 'This reason must add stock (positive number)';
    else if (form.reason === 'DAMAGED' && change > 0) next.quantity_change = 'This reason must remove stock (negative number)';
    else if (product.stock_quantity + change < 0) next.quantity_change = `Only ${product.stock_quantity} in stock - this would make it negative`;
    if (form.reason === 'OTHER' && !form.note.trim()) next.note = 'A note is required for “Other”';
    return next;
  };

  const submit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    const clientErrors = validate();
    setErrors(clientErrors);
    setError(null);
    if (Object.keys(clientErrors).length) return;

    const ok = await confirm({
      title: 'Adjust stock?',
      message: (
        <>
          <p>
            <strong>{product.name}</strong>: {product.stock_quantity} → <strong>{product.stock_quantity + change}</strong> ({change > 0 ? '+' : ''}
            {change}, {REASON_LABELS[form.reason].toLowerCase()})
          </p>
          <p className="muted">This is recorded permanently in the stock history under your name.</p>
        </>
      ),
      confirmLabel: 'Record adjustment',
    });
    if (!ok) return;

    setSubmitting(true);
    try {
      await api.products.adjust(workspaceId, product.id, {
        quantity_change: change,
        reason: form.reason,
        note: form.note.trim() || null,
      });
      toast.success('Stock adjusted');
      setForm({ quantity_change: '', reason: form.reason, note: '' });
      onDone();
    } catch (err) {
      setError(err);
      setErrors(err.fieldErrors || {});
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="form-grid">
      {error && !Object.keys(errors).length && <ErrorBanner error={error} />}
      <SelectField
        label="Reason"
        value={form.reason}
        onChange={(e) => setForm({ ...form, reason: e.target.value })}
        hint={REASON_HINT[form.reason]}
      >
        {MANUAL_REASONS.map((r) => (
          <option key={r} value={r}>
            {REASON_LABELS[r]}
          </option>
        ))}
      </SelectField>
      <Field label="Quantity change" error={errors.quantity_change} hint={form.quantity_change && !errors.quantity_change && Number.isFinite(change) ? `New stock would be ${product.stock_quantity + change}` : 'Positive adds, negative removes.'}>
        {(a11y) => <input {...a11y} inputMode="numeric" value={form.quantity_change} onChange={(e) => setForm({ ...form, quantity_change: e.target.value })} placeholder="e.g. 10 or -3" />}
      </Field>
      <div className="span-2">
        <Field label="Note" error={errors.note}>
          {(a11y) => <input {...a11y} maxLength={500} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="Optional, e.g. delivery reference" />}
        </Field>
      </div>
      <div className="form-actions span-2">
        <button className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Saving…' : 'Review & record'}
        </button>
      </div>
    </form>
  );
}

export default function ProductDetail() {
  const { productId } = useParams();
  const { workspaceId, can } = useCurrentWorkspace();
  const confirm = useConfirm();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ reason: '', date_from: '', date_to: '' });
  const [toggling, setToggling] = useState(false);

  const product = useApi(() => api.products.get(workspaceId, productId), [workspaceId, productId]);
  const dateInvalid = filters.date_from && filters.date_to && filters.date_from > filters.date_to;
  const history = useApi(
    () => api.products.history(workspaceId, productId, { page, page_size: PAGE_SIZE, ...filters }),
    [workspaceId, productId, page, filters.reason, filters.date_from, filters.date_to],
    { enabled: !dateInvalid },
  );

  if (product.loading && !product.data) return <Loading label="Loading product…" />;
  if (product.error) {
    return (
      <>
        <ErrorBanner error={product.error} onRetry={product.refetch} />
        <Link to={`/w/${workspaceId}/products`}>← Back to products</Link>
      </>
    );
  }
  const p = product.data;

  const refreshAll = () => {
    product.refetch();
    setPage(1);
    history.refetch();
  };

  const save = async (payload) => {
    const { stock_quantity, ...rest } = payload; // stock is never edited here
    await api.products.update(workspaceId, p.id, rest);
    toast.success('Product updated');
    setEditing(false);
    product.refetch();
  };

  const toggleActive = async () => {
    const deactivating = p.is_active;
    const ok = await confirm({
      title: deactivating ? 'Deactivate product?' : 'Reactivate product?',
      message: deactivating
        ? 'It can no longer be added to new orders. Existing orders and stock history are kept.'
        : 'It will be available for new orders again.',
      confirmLabel: deactivating ? 'Deactivate' : 'Reactivate',
      danger: deactivating,
    });
    if (!ok) return;
    setToggling(true);
    try {
      await api.products.update(workspaceId, p.id, { is_active: !p.is_active });
      toast.success(deactivating ? 'Product deactivated' : 'Product reactivated');
      product.refetch();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setToggling(false);
    }
  };

  return (
    <>
      <p>
        <Link to={`/w/${workspaceId}/products`}>← Products</Link>
      </p>
      <div className="page-header">
        <div>
          <h1>
            {p.name} {p.is_low_stock && <LowStockBadge />} {!p.is_active && <InactiveBadge />}
          </h1>
          <div className="muted">
            SKU <code>{p.sku}</code>
          </div>
        </div>
        {can('product:write') && !editing && (
          <div className="btn-row">
            <button className="btn" onClick={() => setEditing(true)}>
              Edit details
            </button>
            <button className={`btn ${p.is_active ? 'btn-danger-outline' : ''}`} onClick={toggleActive} disabled={toggling}>
              {p.is_active ? 'Deactivate' : 'Reactivate'}
            </button>
          </div>
        )}
      </div>

      <section className="stat-grid">
        <div className="card stat">
          <div className="stat-label">In stock</div>
          <div className={`stat-value ${p.is_low_stock ? 'stock-low' : ''}`}>{p.stock_quantity}</div>
          <div className="stat-hint">Alert at ≤ {p.low_stock_threshold}</div>
        </div>
        <div className="card stat">
          <div className="stat-label">Unit price</div>
          <div className="stat-value">{formatMoney(p.unit_price)}</div>
          <div className="stat-hint">Past orders keep their original price</div>
        </div>
      </section>

      {editing ? (
        <section className="card">
          <h2>Edit details</h2>
          <ProductForm mode="edit" initial={p} submitLabel="Save changes" onSubmit={save} onCancel={() => setEditing(false)} />
        </section>
      ) : (
        p.description && (
          <section className="card">
            <h2>Description</h2>
            <p>{p.description}</p>
          </section>
        )
      )}

      {can('inventory:adjust') && (
        <section className="card">
          <h2>Adjust stock</h2>
          <p className="muted small">Current stock only changes through recorded adjustments and order activity.</p>
          <AdjustStock product={p} workspaceId={workspaceId} onDone={refreshAll} />
        </section>
      )}

      <section className="card">
        <h2>Stock history</h2>
        <div className="filters inline">
          <div className="field">
            <label htmlFor="h-reason">Reason</label>
            <select id="h-reason" value={filters.reason} onChange={(e) => { setPage(1); setFilters({ ...filters, reason: e.target.value }); }}>
              <option value="">All</option>
              {Object.entries(REASON_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="h-from">From (UTC)</label>
            <input id="h-from" type="date" value={filters.date_from} onChange={(e) => { setPage(1); setFilters({ ...filters, date_from: e.target.value }); }} />
          </div>
          <div className="field">
            <label htmlFor="h-to">To (UTC)</label>
            <input id="h-to" type="date" value={filters.date_to} onChange={(e) => { setPage(1); setFilters({ ...filters, date_to: e.target.value }); }} />
          </div>
        </div>
        {dateInvalid && <div className="banner banner-error" role="alert">“From” must not be after “To”.</div>}
        <ErrorBanner error={history.error} onRetry={history.refetch} />
        {history.loading && !history.data && <Loading label="Loading history…" />}
        {history.data && history.data.items.length === 0 && <EmptyState title="No stock movements for these filters" />}
        {history.data && history.data.items.length > 0 && (
          <div className={history.loading ? 'refreshing' : undefined}>
            <HistoryTable rows={history.data.items} workspaceId={workspaceId} />
            <Pagination page={history.data.page} pages={history.data.pages} total={history.data.total} pageSize={history.data.page_size} onChange={setPage} />
          </div>
        )}
      </section>
    </>
  );
}
