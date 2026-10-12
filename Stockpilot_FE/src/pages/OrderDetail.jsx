import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { StatusBadge } from '../components/Badges.jsx';
import { ErrorBanner, Loading } from '../components/States.jsx';
import { useConfirm } from '../context/ConfirmContext.jsx';
import { useCurrentWorkspace } from '../context/WorkspaceContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { useApi } from '../hooks/useApi.js';
import { formatDateTime } from '../utils/format.js';
import { formatMoney } from '../utils/money.js';

// Which actions are offered in each status. The server enforces the same lifecycle.
const ACTIONS = {
  PENDING: ['confirm', 'cancel'],
  CONFIRMED: ['complete', 'cancel'],
  COMPLETED: [],
  CANCELLED: [],
};

const ACTION_COPY = {
  confirm: {
    label: 'Confirm order',
    title: 'Confirm this order?',
    message: 'The order moves to Confirmed. Stock was already reserved when the order was placed, so it is not deducted again.',
    done: 'Order confirmed',
  },
  complete: {
    label: 'Mark completed',
    title: 'Complete this order?',
    message: 'The order is finished and can no longer be changed or cancelled. The reserved stock stays deducted.',
    done: 'Order completed',
  },
  cancel: {
    label: 'Cancel order',
    title: 'Cancel this order?',
    message: 'The reserved stock is returned to inventory. A cancelled order cannot be reopened.',
    done: 'Order cancelled and stock restored',
    danger: true,
    confirmLabel: 'Cancel order',
    cancelLabel: 'Keep order',
  },
};

export default function OrderDetail() {
  const { orderId } = useParams();
  const { workspaceId, can } = useCurrentWorkspace();
  const confirm = useConfirm();
  const toast = useToast();
  const [busy, setBusy] = useState(null);
  const { data: order, error, loading, refetch } = useApi(() => api.orders.get(workspaceId, orderId), [workspaceId, orderId]);

  if (loading && !order) return <Loading label="Loading order…" />;
  if (error && !order) {
    return (
      <>
        <ErrorBanner error={error} onRetry={refetch} />
        <Link to={`/w/${workspaceId}/orders`}>← Back to orders</Link>
      </>
    );
  }

  const run = async (action) => {
    const copy = ACTION_COPY[action];
    const ok = await confirm({
      title: copy.title,
      message: <p>{copy.message}</p>,
      confirmLabel: copy.confirmLabel || copy.label,
      cancelLabel: copy.cancelLabel,
      danger: copy.danger,
    });
    if (!ok) return;
    setBusy(action);
    try {
      await api.orders.transition(workspaceId, order.id, action);
      toast.success(copy.done);
    } catch (err) {
      toast.error(err.message); // e.g. someone else already changed the order
    } finally {
      setBusy(null);
      refetch(); // always show the true server state
    }
  };

  const actions = can('order:update') ? ACTIONS[order.status] : [];

  return (
    <>
      <p>
        <Link to={`/w/${workspaceId}/orders`}>← Orders</Link>
      </p>
      <div className="page-header">
        <div>
          <h1>
            Order {order.display_number} <StatusBadge status={order.status} />
          </h1>
          <div className="muted">
            Placed by {order.creator.full_name} on {formatDateTime(order.created_at)}
          </div>
        </div>
        {actions.length > 0 && (
          <div className="btn-row">
            {actions.map((a) => (
              <button
                key={a}
                className={`btn ${a === 'cancel' ? 'btn-danger-outline' : 'btn-primary'}`}
                disabled={busy !== null}
                onClick={() => run(a)}
              >
                {busy === a ? 'Working…' : ACTION_COPY[a].label}
              </button>
            ))}
          </div>
        )}
      </div>

      <ErrorBanner error={error} onRetry={refetch} />

      {order.status === 'COMPLETED' && <div className="banner banner-info">This order is completed and can no longer be changed.</div>}
      {order.status === 'CANCELLED' && <div className="banner banner-info">This order was cancelled; its reserved stock was returned to inventory.</div>}

      <section className="card">
        <h2>Items</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>SKU</th>
                <th className="num">Unit price</th>
                <th className="num">Qty</th>
                <th className="num">Line total</th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((i) => (
                <tr key={i.id}>
                  <td>
                    <Link to={`/w/${workspaceId}/products/${i.product_id}`}>{i.product_name}</Link>
                  </td>
                  <td>
                    <code>{i.sku}</code>
                  </td>
                  <td className="num">{formatMoney(i.unit_price)}</td>
                  <td className="num">{i.quantity}</td>
                  <td className="num">{formatMoney(i.line_total)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th colSpan={4} className="num">
                  Total
                </th>
                <th className="num">{formatMoney(order.total_amount)}</th>
              </tr>
            </tfoot>
          </table>
        </div>
        <p className="muted small">Names, SKUs and prices are the values at the time the order was placed.</p>
        {order.notes && (
          <p>
            <strong>Notes:</strong> {order.notes}
          </p>
        )}
      </section>

      <section className="card">
        <h2>Timeline</h2>
        <ul className="timeline">
          <li>Placed — {formatDateTime(order.created_at)}</li>
          {order.confirmed_at && <li>Confirmed — {formatDateTime(order.confirmed_at)}</li>}
          {order.completed_at && <li>Completed — {formatDateTime(order.completed_at)}</li>}
          {order.cancelled_at && <li>Cancelled — {formatDateTime(order.cancelled_at)}</li>}
        </ul>
      </section>
    </>
  );
}
