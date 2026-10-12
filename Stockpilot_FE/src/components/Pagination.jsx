// Page numbers to show: always first and last, plus a window around the current page, with "…" gaps.
function pageList(page, pages) {
  const wanted = new Set([1, pages, page - 1, page, page + 1]);
  const numbers = [...wanted].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b);
  const out = [];
  numbers.forEach((n, i) => {
    if (i > 0 && n - numbers[i - 1] > 1) out.push('gap-' + n);
    out.push(n);
  });
  return out;
}

export default function Pagination({ page, pages, total, pageSize, onChange }) {
  if (!total) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <nav className="pagination" aria-label="Pagination">
      <span className="muted small">
        Showing {from}–{to} of {total}
      </span>
      {pages > 1 && (
        <div className="pagination-buttons">
          <button className="btn btn-small" disabled={page <= 1} onClick={() => onChange(page - 1)}>
            ← Previous
          </button>
          {pageList(page, pages).map((item) =>
            typeof item === 'string' ? (
              <span key={item} className="page-gap" aria-hidden="true">
                …
              </span>
            ) : (
              <button
                key={item}
                className={`btn btn-small page-number${item === page ? ' current' : ''}`}
                aria-current={item === page ? 'page' : undefined}
                aria-label={`Page ${item}`}
                onClick={() => item !== page && onChange(item)}
              >
                {item}
              </button>
            ),
          )}
          <button className="btn btn-small" disabled={page >= pages} onClick={() => onChange(page + 1)}>
            Next →
          </button>
        </div>
      )}
    </nav>
  );
}
