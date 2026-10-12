import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { InactiveBadge, LowStockBadge, StockCell } from '../components/Badges.jsx';
import Pagination from '../components/Pagination.jsx';
import { EmptyState, ErrorBanner, Loading } from '../components/States.jsx';
import { useCurrentWorkspace } from '../context/WorkspaceContext.jsx';
import { useApi, useDebounce } from '../hooks/useApi.js';
import { PAGE_SIZE } from '../utils/format.js';
import { formatMoney } from '../utils/money.js';

const SORTS = {
  'name:asc': 'Name (A–Z)',
  'name:desc': 'Name (Z–A)',
  'stock_quantity:asc': 'Stock (low → high)',
  'stock_quantity:desc': 'Stock (high → low)',
  'unit_price:asc': 'Price (low → high)',
  'unit_price:desc': 'Price (high → low)',
  'created_at:desc': 'Newest first',
};

export default function Products() {
  const { workspaceId, can } = useCurrentWorkspace();
  const [params, setParams] = useSearchParams();
  const page = Number(params.get('page')) || 1;
  const active = params.get('active') || 'all';
  const lowStock = params.get('low_stock') === 'true';
  const sort = params.get('sort') || 'name:asc';
  const urlQuery = params.get('q') || '';

  const [search, setSearch] = useState(urlQuery);
  const debouncedSearch = useDebounce(search, 300);

  const update = (changes) => {
    const next = new URLSearchParams(params);
    Object.entries({ page: 1, ...changes }).forEach(([k, v]) => {
      if (v === '' || v === null || v === undefined || v === false || (k === 'page' && v === 1) || (k === 'active' && v === 'all')) next.delete(k);
      else next.set(k, String(v));
    });
    setParams(next, { replace: true });
  };

  useEffect(() => {
    if (debouncedSearch !== urlQuery) update({ q: debouncedSearch.trim() });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  const [sort_by, sort_dir] = sort.split(':');
  const { data, error, loading, refetch } = useApi(
    () =>
      api.products.list(workspaceId, {
        page,
        page_size: PAGE_SIZE,
        q: urlQuery,
        active,
        low_stock: lowStock ? true : undefined,
        sort_by,
        sort_dir,
      }),
    [workspaceId, page, urlQuery, active, lowStock, sort],
  );

  const filtered = Boolean(urlQuery || lowStock || active !== 'all');

  return (
    <>
      <div className="page-header">
        <h1>Products</h1>
        {can('product:write') && (
          <Link className="btn btn-primary" to={`/w/${workspaceId}/products/new`}>
            ＋ New product
          </Link>
        )}
      </div>

      <div className="card filters">
        <div className="field">
          <label htmlFor="product-search">Search name or SKU</label>
          <input id="product-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="e.g. hammer or HAM-016" />
        </div>
        <div className="field">
          <label htmlFor="product-active">Status</label>
          <select id="product-active" value={active} onChange={(e) => update({ active: e.target.value })}>
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="product-sort">Sort by</label>
          <select id="product-sort" value={sort} onChange={(e) => update({ sort: e.target.value })}>
            {Object.entries(SORTS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <label className="check">
          <input type="checkbox" checked={lowStock} onChange={(e) => update({ low_stock: e.target.checked })} /> Low stock only
        </label>
        {filtered && (
          <button
            className="btn btn-small"
            onClick={() => {
              setSearch('');
              setParams({}, { replace: true });
            }}
          >
            Clear filters
          </button>
        )}
      </div>

      <ErrorBanner error={error} onRetry={refetch} />
      {loading && !data && <Loading label="Loading products…" />}

      {data && data.items.length === 0 && (
        <div className="card">
          <EmptyState
            title={filtered ? 'No products match these filters' : 'No products yet'}
            action={
              !filtered && can('product:write') ? (
                <Link className="btn btn-primary" to={`/w/${workspaceId}/products/new`}>
                  Add your first product
                </Link>
              ) : null
            }
          >
            {filtered ? 'Try a different search or clear the filters.' : can('product:write') ? 'Create a product to start tracking stock.' : 'An admin needs to add products first.'}
          </EmptyState>
        </div>
      )}

      {data && data.items.length > 0 && (
        <div className={`card ${loading ? 'refreshing' : ''}`}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>SKU</th>
                  <th className="num">Price</th>
                  <th className="num">In stock</th>
                  <th className="num">Alert at</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.id} className={p.is_active ? undefined : 'row-muted'}>
                    <td>
                      <Link to={`/w/${workspaceId}/products/${p.id}`}>{p.name}</Link>
                    </td>
                    <td>
                      <code>{p.sku}</code>
                    </td>
                    <td className="num">{formatMoney(p.unit_price)}</td>
                    <td className="num">
                      <StockCell product={p} />
                    </td>
                    <td className="num">≤ {p.low_stock_threshold}</td>
                    <td className="flags">
                      {p.is_low_stock && <LowStockBadge />}
                      {!p.is_active && <InactiveBadge />}
                    </td>
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
