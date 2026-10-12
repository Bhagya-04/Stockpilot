import { useState } from 'react';
import { Field, TextField } from './FormField.jsx';
import { ErrorBanner } from './States.jsx';
import { toCents } from '../utils/money.js';

const SKU_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/;
const isNonNegativeInt = (v) => /^\d+$/.test(String(v).trim());

/**
 * Create / edit form. Client-side checks only improve feedback; the server validates everything again.
 * Stock is editable only when creating (opening balance) - afterwards it changes via stock adjustments.
 */
export default function ProductForm({ initial, mode, onSubmit, onCancel, submitLabel }) {
  const [values, setValues] = useState({
    name: initial?.name ?? '',
    sku: initial?.sku ?? '',
    description: initial?.description ?? '',
    unit_price: initial?.unit_price ?? '',
    stock_quantity: '0',
    low_stock_threshold: String(initial?.low_stock_threshold ?? 0),
    is_active: initial?.is_active ?? true,
  });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const set = (field) => (e) => setValues({ ...values, [field]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });

  const validate = () => {
    const next = {};
    if (!values.name.trim()) next.name = 'Name is required';
    if (!values.sku.trim()) next.sku = 'SKU is required';
    else if (!SKU_PATTERN.test(values.sku.trim())) next.sku = 'Use letters, digits and . _ / - only';
    if (toCents(values.unit_price) === null) next.unit_price = 'Enter a price like 12.50 (max 2 decimals, not negative)';
    if (mode === 'create' && !isNonNegativeInt(values.stock_quantity)) next.stock_quantity = 'Whole number, 0 or more';
    if (!isNonNegativeInt(values.low_stock_threshold)) next.low_stock_threshold = 'Whole number, 0 or more';
    return next;
  };

  const submit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    const clientErrors = validate();
    setErrors(clientErrors);
    setError(null);
    if (Object.keys(clientErrors).length) return;

    const payload = {
      name: values.name.trim(),
      sku: values.sku.trim(),
      description: values.description.trim() || null,
      unit_price: values.unit_price.trim(),
      low_stock_threshold: Number(values.low_stock_threshold),
      is_active: values.is_active,
    };
    if (mode === 'create') payload.stock_quantity = Number(values.stock_quantity);

    setSubmitting(true);
    try {
      await onSubmit(payload);
    } catch (err) {
      setError(err);
      setErrors(err.fieldErrors || {});
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="form-grid">
      {error && !Object.keys(errors).length && <ErrorBanner error={error} />}
      <TextField label="Product name" value={values.name} onChange={set('name')} error={errors.name} maxLength={200} required />
      <TextField
        label="SKU"
        value={values.sku}
        onChange={set('sku')}
        error={errors.sku}
        hint="Unique within this workspace. Stored in upper case."
        maxLength={64}
        required
      />
      <TextField
        label="Unit price"
        inputMode="decimal"
        value={values.unit_price}
        onChange={set('unit_price')}
        error={errors.unit_price}
        placeholder="0.00"
        required
      />
      {mode === 'create' && (
        <TextField
          label="Opening stock"
          inputMode="numeric"
          value={values.stock_quantity}
          onChange={set('stock_quantity')}
          error={errors.stock_quantity}
          hint="Recorded in the stock history as the opening balance."
        />
      )}
      <TextField
        label="Low-stock threshold"
        inputMode="numeric"
        value={values.low_stock_threshold}
        onChange={set('low_stock_threshold')}
        error={errors.low_stock_threshold}
        hint="Flagged as low stock when stock is at or below this number."
      />
      <div className="span-2">
        <Field label="Description" error={errors.description}>
          {(a11y) => <textarea {...a11y} rows={3} maxLength={2000} value={values.description} onChange={set('description')} />}
        </Field>
      </div>
      <label className="check span-2">
        <input type="checkbox" checked={values.is_active} onChange={set('is_active')} /> Active (available for new orders)
      </label>
      <div className="form-actions span-2">
        {onCancel && (
          <button type="button" className="btn" onClick={onCancel} disabled={submitting}>
            Cancel
          </button>
        )}
        <button className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  );
}
