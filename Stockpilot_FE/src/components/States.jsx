export function Loading({ label = 'Loading…' }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ title, children, action }) {
  return (
    <div className="state empty">
      <strong>{title}</strong>
      {children && <p className="muted">{children}</p>}
      {action}
    </div>
  );
}

/** Shows an ApiError (or any Error): the message plus any details not tied to a form field. */
export function ErrorBanner({ error, onRetry }) {
  if (!error) return null;
  const details = error.generalDetails || [];
  return (
    <div className="banner banner-error" role="alert">
      <div>
        <strong>{error.message}</strong>
        {details.length > 0 && (
          <ul>
            {details.map((d, i) => (
              <li key={i}>{d.message}</li>
            ))}
          </ul>
        )}
        {error.requestId && <div className="muted small">Reference: {error.requestId}</div>}
      </div>
      {onRetry && (
        <button className="btn btn-small" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
