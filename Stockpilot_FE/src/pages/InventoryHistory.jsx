import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client.js';
import HistoryTable from '../components/HistoryTable.jsx';
import Pagination from '../components/Pagination.jsx';
import { EmptyState, ErrorBanner, Loading } from '../components/States.jsx';
import { useCurrentWorkspace } from '../context/WorkspaceContext.jsx';
import { useApi } from '../hooks/useApi.js';
import { PAGE_SIZE, REASON_LABELS } from '../utils/format.js';

export default function InventoryHistory() {
  const { workspaceId } = useCurrentWorkspace();
  const [params] = useSearchParams();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ product_id: params.get('product_id') || '', reason: '', date_from: '', date_to: '' });
  const dateInvalid = filters.date_from && filters.date_to && filters.date_from > filters.date_to;

  // Product picker: first 100 products by name (enough for the demo; see README for the trade-off).
  const products = useApi(() => api.products.list(workspaceId, { page_size: 100, sort_by: 'name', sort_dir: 'asc' }), [workspaceId]);
  const history = useApi(
    () => api.inventory.history(workspaceId, { page, page_size: PAGE_SIZE, ...filters }),
    [workspaceId, page, filters.product_id, filters.reason, filters.date_from, filters.date_to],
    { enabled: !dateInvalid },
  );

  const change = (field) => (e) => {
    setPage(1);
    setFilters({ ...filters, [field]: e.target.value });
  };
  const filtered = Object.values(filters).some(Boolean);

  return (
    <>
      <div className="page-header">
        <h1>Stock history</h1>
      </div>
      <p className="muted small">Every change to stock - manual adjustments, opening balances, and order reservations/cancellations - newest first.</p>

      <div className="card filters">
        <div className="field">
          <label htmlFor="f-product">Product</label>
          <select id="f-product" value={filters.product_id} onChange={change('product_id')}>
            <option value="">All products</option>
            {(products.data?.items || []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.sku})
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-reason">Reason</label>
          <select id="f-reason" value={filters.reason} onChange={change('reason')}>
            <option value="">All</option>
            {Object.entries(REASON_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-from">From (UTC)</label>
          <input id="f-from" type="date" value={filters.date_from} onChange={change('date_from')} />
        </div>
        <div className="field">
          <label htmlFor="f-to">To (UTC)</label>
          <input id="f-to" type="date" value={filters.date_to} onChange={change('date_to')} />
        </div>
        {filtered && (
          <button className="btn btn-small" onClick={() => { setPage(1); setFilters({ product_id: '', reason: '', date_from: '', date_to: '' }); }}>
            Clear filters
          </button>
        )}
      </div>

      {dateInvalid && <div className="banner banner-error" role="alert">“From” must not be after “To”.</div>}
      <ErrorBanner error={history.error} onRetry={history.refetch} />
      {history.loading && !history.data && <Loading label="Loading history…" />}
      {history.data && history.data.items.length === 0 && (
        <div className="card">
          <EmptyState title={filtered ? 'No stock movements match these filters' : 'No stock movements yet'} />
        </div>
      )}
      {history.data && history.data.items.length > 0 && (
        <div className={`card ${history.loading ? 'refreshing' : ''}`}>
          <HistoryTable rows={history.data.items} workspaceId={workspaceId} showProduct />
          <Pagination page={history.data.page} pages={history.data.pages} total={history.data.total} pageSize={history.data.page_size} onChange={setPage} />
        </div>
      )}
    </>
  );
}
