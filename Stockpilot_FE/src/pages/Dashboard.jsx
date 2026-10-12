import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { StatusBadge } from '../components/Badges.jsx';
import { EmptyState, ErrorBanner, Loading } from '../components/States.jsx';
import { useCurrentWorkspace } from '../context/WorkspaceContext.jsx';
import { useApi } from '../hooks/useApi.js';
import { formatDateTime, ORDER_STATUSES, REASON_LABELS, utcDateString } from '../utils/format.js';
import { formatMoney } from '../utils/money.js';

function Stat({ label, value, hint, to }) {
  const body = (
    <>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </>
  );
  return to ? (
    <Link to={to} className="card stat stat-link">
      {body}
    </Link>
  ) : (
    <div className="card stat">{body}</div>
  );
}

export default function Dashboard() {
  const { workspaceId } = useCurrentWorkspace();
  const [range, setRange] = useState({ date_from: utcDateString(29), date_to: utcDateString(0) });
  const rangeInvalid = range.date_from && range.date_to && range.date_from > range.date_to;

  const { data, error, loading, refetch } = useApi(
    () => api.dashboard.get(workspaceId, range),
    [workspaceId, range.date_from, range.date_to],
    { enabled: !rangeInvalid },
  );

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <form className="inline-form" onSubmit={(e) => e.preventDefault()}>
          <label>
            From <input type="date" value={range.date_from} max={range.date_to || undefined} onChange={(e) => setRange({ ...range, date_from: e.target.value })} />
          </label>
          <label>
            To <input type="date" value={range.date_to} min={range.date_from || undefined} onChange={(e) => setRange({ ...range, date_to: e.target.value })} />
          </label>
        </form>
      </div>
      <p className="muted small">Order figures cover orders created in the selected range (dates are UTC days, both ends included).</p>

      {rangeInvalid && <div className="banner banner-error" role="alert">“From” must not be after “To”.</div>}
      <ErrorBanner error={error} onRetry={refetch} />
      {loading && !data && <Loading label="Loading dashboard…" />}

      {data && (
        <div className={loading ? 'refreshing' : undefined}>
          <section className="stat-grid" aria-label="Key metrics">
            <Stat label="Active products" value={data.total_active_products} to={`/w/${workspaceId}/products?active=active`} />
            <Stat
              label="Low-stock products"
              value={data.low_stock_products}
              hint="Active, at or below threshold"
              to={`/w/${workspaceId}/products?low_stock=true`}
            />
            <Stat label="Order value" value={formatMoney(data.order_value)} hint="Pending + confirmed + completed (cancelled excluded)" />
            <Stat label="Completed value" value={formatMoney(data.completed_order_value)} hint="Completed orders only" />
          </section>

          <section className="card">
            <h2>Orders by status</h2>
            <div className="status-row">
              {ORDER_STATUSES.map((s) => (
                <Link key={s} to={`/w/${workspaceId}/orders?status=${s}`} className="status-count">
                  <StatusBadge status={s} />
                  <strong>{data.order_counts_by_status[s] ?? 0}</strong>
                </Link>
              ))}
            </div>
          </section>

          <div className="two-col">
            <section className="card">
              <div className="section-header">
                <h2>Recent orders</h2>
                <Link to={`/w/${workspaceId}/orders`}>View all</Link>
              </div>
              {data.recent_orders.length === 0 ? (
                <EmptyState title="No orders yet">Orders you create will show up here.</EmptyState>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Order</th>
                        <th>Status</th>
                        <th className="num">Total</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_orders.map((o) => (
                        <tr key={o.id}>
                          <td>
                            <Link to={`/w/${workspaceId}/orders/${o.id}`}>{o.display_number}</Link>
                          </td>
                          <td>
                            <StatusBadge status={o.status} />
                          </td>
                          <td className="num">{formatMoney(o.total_amount)}</td>
                          <td>{formatDateTime(o.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="card">
              <div className="section-header">
                <h2>Recent stock changes</h2>
                <Link to={`/w/${workspaceId}/inventory`}>View all</Link>
              </div>
              {data.recent_adjustments.length === 0 ? (
                <EmptyState title="No stock movements yet">Adjustments and order activity will show up here.</EmptyState>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th className="num">Change</th>
                        <th>Reason</th>
                        <th>When</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_adjustments.map((a) => (
                        <tr key={a.id}>
                          <td>
                            <Link to={`/w/${workspaceId}/products/${a.product.id}`}>{a.product.name}</Link>
                          </td>
                          <td className={`num ${a.quantity_change < 0 ? 'neg' : 'pos'}`}>
                            {a.quantity_change > 0 ? '+' : ''}
                            {a.quantity_change}
                          </td>
                          <td>{REASON_LABELS[a.reason] || a.reason}</td>
                          <td>{formatDateTime(a.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        </div>
      )}
    </>
  );
}
