import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { StatusBadge } from '../components/Badges.jsx';
import Pagination from '../components/Pagination.jsx';
import { EmptyState, ErrorBanner, Loading } from '../components/States.jsx';
import { useCurrentWorkspace } from '../context/WorkspaceContext.jsx';
import { useApi, useDebounce } from '../hooks/useApi.js';
import { formatDateTime, ORDER_STATUSES, PAGE_SIZE, STATUS_LABELS } from '../utils/format.js';
import { formatMoney } from '../utils/money.js';

export default function Orders() {
  const { workspaceId, can } = useCurrentWorkspace();
  const [params, setParams] = useSearchParams();
  const page = Number(params.get('page')) || 1;
  const status = params.get('status') || '';
  const dateFrom = params.get('date_from') || '';
  const dateTo = params.get('date_to') || '';
  const urlQuery = params.get('q') || '';
  const sort = params.get('sort') || 'created_at:desc';

  const [search, setSearch] = useState(urlQuery);
  const debounced = useDebounce(search, 300);
  const dateInvalid = dateFrom && dateTo && dateFrom > dateTo;

  const update = (changes) => {
    const next = new URLSearchParams(params);
    Object.entries({ page: 1, ...changes }).forEach(([k, v]) => {
      if (v === '' || v == null || (k === 'page' && v === 1)) next.delete(k);
      else next.set(k, String(v));
    });
    setParams(next, { replace: true });
  };

  useEffect(() => {
    if (debounced.trim() !== urlQuery) update({ q: debounced.trim() });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const [sort_by, sort_dir] = sort.split(':');
  const { data, error, loading, refetch } = useApi(
    () => api.orders.list(workspaceId, { page, page_size: PAGE_SIZE, status, q: urlQuery, date_from: dateFrom, date_to: dateTo, sort_by, sort_dir }),
    [workspaceId, page, status, urlQuery, dateFrom, dateTo, sort],
    { enabled: !dateInvalid },
  );

  const filtered = Boolean(status || urlQuery || dateFrom || dateTo);

  return (
    <>
      <div className="page-header">
        <h1>Orders</h1>
        {can('order:create') && (
          <Link className="btn btn-primary" to={`/w/${workspaceId}/orders/new`}>
            ＋ New order
          </Link>
        )}
      </div>

      <div className="card filters">
        <div className="field">
          <label htmlFor="o-search">Order number</label>
          <input id="o-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="e.g. ORD-000012" />
        </div>
        <div className="field">
          <label htmlFor="o-status">Status</label>
          <select id="o-status" value={status} onChange={(e) => update({ status: e.target.value })}>
            <option value="">All statuses</option>
            {ORDER_STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="o-from">Created from (UTC)</label>
          <input id="o-from" type="date" value={dateFrom} onChange={(e) => update({ date_from: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="o-to">Created to (UTC)</label>
          <input id="o-to" type="date" value={dateTo} onChange={(e) => update({ date_to: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="o-sort">Sort by</label>
          <select id="o-sort" value={sort} onChange={(e) => update({ sort: e.target.value })}>
            <option value="created_at:desc">Newest first</option>
            <option value="created_at:asc">Oldest first</option>
            <option value="total_amount:desc">Total (high → low)</option>
            <option value="total_amount:asc">Total (low → high)</option>
          </select>
        </div>
        {filtered && (
          <button className="btn btn-small" onClick={() => { setSearch(''); setParams({}, { replace: true }); }}>
            Clear filters
          </button>
        )}
      </div>

      {dateInvalid && <div className="banner banner-error" role="alert">“From” must not be after “To”.</div>}
      <ErrorBanner error={error} onRetry={refetch} />
      {loading && !data && <Loading label="Loading orders…" />}

      {data && data.items.length === 0 && (
        <div className="card">
          <EmptyState
            title={filtered ? 'No orders match these filters' : 'No orders yet'}
            action={
              !filtered && can('order:create') ? (
                <Link className="btn btn-primary" to={`/w/${workspaceId}/orders/new`}>
                  Create the first order
                </Link>
              ) : null
            }
          >
            {filtered ? 'Try different filters.' : 'Orders you create will appear here.'}
          </EmptyState>
        </div>
      )}

      {data && data.items.length > 0 && (
        <div className={`card ${loading ? 'refreshing' : ''}`}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Status</th>
                  <th className="num">Items</th>
                  <th className="num">Total</th>
                  <th>Created by</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <Link to={`/w/${workspaceId}/orders/${o.id}`}>{o.display_number}</Link>
                    </td>
                    <td>
                      <StatusBadge status={o.status} />
                    </td>
                    <td className="num">{o.items.length}</td>
                    <td className="num">{formatMoney(o.total_amount)}</td>
                    <td>{o.creator.full_name}</td>
                    <td>{formatDateTime(o.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onChange={(p) => update({ page: p })} />
        </div>
      )}
    </>
  );
}
