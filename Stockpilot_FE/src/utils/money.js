// Money helpers. Prices arrive from the API as exact decimal strings ("19.99").
// Arithmetic is done on integer cents - never on floats - and is only ever a PREVIEW:
// the server computes the authoritative totals.

// Display only: amounts are stored and computed as exact decimals / integer cents regardless of currency.
const CURRENCY = import.meta.env?.VITE_CURRENCY || 'INR';
const LOCALE = import.meta.env?.VITE_LOCALE || 'en-IN'; // en-IN groups digits Indian-style: ₹1,23,456.00

/** "19.99" -> 1999. Returns null if the text is not a valid non-negative amount with <= 2 decimals. */
export function toCents(text) {
  const match = /^(\d{1,9})(?:\.(\d{1,2}))?$/.exec(String(text ?? '').trim());
  if (!match) return null;
  const cents = match[2] ? match[2].padEnd(2, '0') : '00';
  return Number(match[1]) * 100 + Number(cents);
}

/** 1999 -> "19.99" */
export function centsToString(cents) {
  const sign = cents < 0 ? '-' : '';
  const abs = Math.abs(cents);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}

export function lineTotalCents(unitPriceText, quantity) {
  const unit = toCents(unitPriceText);
  if (unit === null || !Number.isInteger(quantity)) return 0;
  return unit * quantity;
}

const formatter = new Intl.NumberFormat(LOCALE, { style: 'currency', currency: CURRENCY });

/** Display an API decimal string (or cents via formatCents) as currency. */
export function formatMoney(decimalText) {
  const cents = toCents(decimalText);
  return formatter.format(cents === null ? 0 : cents / 100);
}

export function formatCents(cents) {
  return formatter.format(cents / 100);
}
