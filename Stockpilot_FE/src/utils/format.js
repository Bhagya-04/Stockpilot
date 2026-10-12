/** Rows per page on every list: page 1 = items 1-10, page 2 = 11-20, ... */
export const PAGE_SIZE = 10;

export function formatDateTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: 'medium' });
}

/** Date input value (YYYY-MM-DD) for "n days ago" in UTC, matching the API's UTC-day convention. */
export function utcDateString(daysAgo = 0) {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - daysAgo);
  return d.toISOString().slice(0, 10);
}

export const REASON_LABELS = {
  RECEIVED: 'Stock received',
  RETURNED: 'Customer return',
  DAMAGED: 'Damaged / lost',
  CORRECTION: 'Count correction',
  OTHER: 'Other',
  INITIAL_STOCK: 'Opening balance',
  ORDER_RESERVED: 'Order placed',
  ORDER_CANCELLED: 'Order cancelled',
};

export const MANUAL_REASONS = ['RECEIVED', 'RETURNED', 'DAMAGED', 'CORRECTION', 'OTHER'];

export const STATUS_LABELS = {
  PENDING: 'Pending',
  CONFIRMED: 'Confirmed',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
};

export const ORDER_STATUSES = Object.keys(STATUS_LABELS);

/** Drop empty values so they are not sent as query parameters. */
export function cleanParams(params) {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined && v !== false),
  );
}
