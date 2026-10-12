import { useId } from 'react';

/** Label + input + inline error. Pass the input as children via render-prop to wire up ids/aria. */
export function Field({ label, error, hint, required, children }) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(' ') || undefined;
  return (
    <div className={`field${error ? ' has-error' : ''}`}>
      <label htmlFor={id}>
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      {children({ id, 'aria-invalid': error ? true : undefined, 'aria-describedby': describedBy })}
      {hint && !error && (
        <div id={hintId} className="hint">
          {hint}
        </div>
      )}
      {error && (
        <div id={errorId} className="field-error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}

export function TextField({ label, error, hint, required, ...inputProps }) {
  return (
    <Field label={label} error={error} hint={hint} required={required}>
      {(a11y) => <input {...a11y} required={required} {...inputProps} />}
    </Field>
  );
}

export function SelectField({ label, error, hint, children, ...selectProps }) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(a11y) => (
        <select {...a11y} {...selectProps}>
          {children}
        </select>
      )}
    </Field>
  );
}
