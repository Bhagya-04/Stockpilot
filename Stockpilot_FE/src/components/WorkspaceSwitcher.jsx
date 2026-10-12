import { useEffect, useRef, useState } from 'react';
/** Custom workspace dropdown (the native <select> list can't be styled to match the sidebar). */
export default function WorkspaceSwitcher({ workspaces, current, onSelect }) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => {
      if (root.current && !root.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const choose = (id) => {
    setOpen(false);
    onSelect(id);
  };

  return (
    <div className="ws-switch" ref={root}>
      <button
        type="button"
        className="ws-button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="ws-avatar" aria-hidden="true">
          {(current?.name || '?')[0].toUpperCase()}
        </span>
        <span className="ws-name-block">
          <span className="ws-name">{current?.name || 'Select workspace'}</span>
          {current && <span className="ws-role-text">{current.role === 'OWNER' ? 'Admin' : 'Staff'}</span>}
        </span>
        <svg className={`ws-chevron${open ? ' open' : ''}`} viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
          <path d="M5 8l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <ul className="ws-menu" role="listbox" aria-label="Workspaces">
          {workspaces.map((w) => (
            <li key={w.id} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={w.id === current?.id}
                className={`ws-option${w.id === current?.id ? ' selected' : ''}`}
                onClick={() => choose(w.id)}
              >
                <span className="ws-avatar small" aria-hidden="true">
                  {w.name[0].toUpperCase()}
                </span>
                <span className="ws-option-text">
                  <span className="ws-option-name">{w.name}</span>
                  <span className="ws-option-role">{w.role === 'OWNER' ? 'Admin' : 'Staff'}</span>
                </span>
                {w.id === current?.id && <span className="ws-check" aria-hidden="true">✓</span>}
              </button>
            </li>
          ))}
          <li className="ws-sep" role="separator" />
          <li role="presentation">
            <button type="button" className="ws-option ws-new" onClick={() => choose('__new')}>
              <span className="ws-plus" aria-hidden="true">＋</span>
              <span>New workspace</span>
            </button>
          </li>
        </ul>
      )}
    </div>
  );
}
