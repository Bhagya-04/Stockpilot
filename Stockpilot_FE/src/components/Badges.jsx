import { STATUS_LABELS } from '../utils/format.js';

// Status is conveyed by text + icon + colour, never colour alone.
const STATUS_ICON = { PENDING: '◔', CONFIRMED: '◑', COMPLETED: '●', CANCELLED: '✕' };

export function StatusBadge({ status }) {
  return (
    <span className={`badge badge-${status.toLowerCase()}`}>
      <span aria-hidden="true">{STATUS_ICON[status]}</span> {STATUS_LABELS[status] || status}
    </span>
  );
}

export function LowStockBadge() {
  return (
    <span className="badge badge-low">
      <span aria-hidden="true">▼</span> Low stock
    </span>
  );
}

export function InactiveBadge() {
  return <span className="badge badge-inactive">Inactive</span>;
}

export function RoleBadge({ role }) {
  return <span className={`badge badge-role-${role.toLowerCase()}`}>{role === 'OWNER' ? 'Admin' : 'Staff'}</span>;
}

/** Stock number that highlights low stock. */
export function StockCell({ product }) {
  return (
    <span className={product.is_low_stock ? 'stock-low' : undefined}>
      {product.stock_quantity}
      {product.is_low_stock && <span className="visually-hidden"> (low stock)</span>}
    </span>
  );
}
