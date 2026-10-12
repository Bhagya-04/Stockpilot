import { Link } from 'react-router-dom';
import { formatDateTime, REASON_LABELS } from '../utils/format.js';

/** Stock-movement ledger rows. `showProduct` adds a product column (workspace-wide view). */
export default function HistoryTable({ rows, workspaceId, showProduct = false }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>When</th>
            {showProduct && <th>Product</th>}
            <th className="num">Change</th>
            <th className="num">Stock after</th>
            <th>Reason</th>
            <th>By</th>
            <th>Note / order</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => (
            <tr key={a.id}>
              <td>{formatDateTime(a.created_at)}</td>
              {showProduct && (
                <td>
                  <Link to={`/w/${workspaceId}/products/${a.product.id}`}>{a.product.name}</Link> <code>{a.product.sku}</code>
                </td>
              )}
              <td className={`num ${a.quantity_change < 0 ? 'neg' : 'pos'}`}>
                {a.quantity_change > 0 ? '+' : ''}
                {a.quantity_change}
              </td>
              <td className="num">{a.resulting_stock}</td>
              <td>{REASON_LABELS[a.reason] || a.reason}</td>
              <td>{a.user.full_name}</td>
              <td>
                {a.order_id ? <Link to={`/w/${workspaceId}/orders/${a.order_id}`}>View order</Link> : null}
                {a.order_id && a.note ? ' · ' : null}
                {a.note}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
