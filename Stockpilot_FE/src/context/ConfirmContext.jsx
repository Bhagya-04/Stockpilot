import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

const ConfirmContext = createContext(null);

/**
 * `const confirm = useConfirm(); if (await confirm({ title, message, confirmLabel, danger })) { ... }`
 * Used for consequential actions (cancelling an order, adjusting stock, deactivating, removing a member).
 */
export function ConfirmProvider({ children }) {
  const [dialog, setDialog] = useState(null);
  const confirmButton = useRef(null);

  const confirm = useCallback(
    (options) => new Promise((resolve) => setDialog({ ...options, resolve })),
    [],
  );

  const close = (result) => {
    dialog.resolve(result);
    setDialog(null);
  };

  useEffect(() => {
    if (!dialog) return undefined;
    confirmButton.current?.focus();
    const onKey = (e) => {
      if (e.key === 'Escape') {
        dialog.resolve(false);
        setDialog(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dialog]);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {dialog && (
        <div className="modal-backdrop" onClick={() => close(false)}>
          <div
            className="modal"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            aria-describedby="confirm-message"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="confirm-title">{dialog.title}</h2>
            <div id="confirm-message" className="modal-body">
              {dialog.message}
            </div>
            <div className="modal-actions">
              <button className="btn" onClick={() => close(false)}>
                {dialog.cancelLabel || 'Go back'}
              </button>
              <button
                ref={confirmButton}
                className={`btn ${dialog.danger ? 'btn-danger' : 'btn-primary'}`}
                onClick={() => close(true)}
              >
                {dialog.confirmLabel || 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  return useContext(ConfirmContext);
}
