import { describe, expect, it } from 'vitest';
import { ApiError } from '../../api/client.js';
import { cleanParams } from '../format.js';
import { centsToString, formatCents, formatMoney, lineTotalCents, toCents } from '../money.js';
import { can } from '../permissions.js';

describe('money (integer cents, no floats)', () => {
  it('parses valid amounts exactly', () => {
    expect(toCents('19.99')).toBe(1999);
    expect(toCents('0.1')).toBe(10);
    expect(toCents('5')).toBe(500);
    expect(toCents('0')).toBe(0);
  });

  it('rejects invalid amounts', () => {
    for (const bad of ['', '-1', '1.234', 'abc', '1,50', null, undefined, '1e3']) {
      expect(toCents(bad)).toBeNull();
    }
  });

  it('avoids floating-point rounding errors', () => {
    // 0.1 * 3 === 0.30000000000000004 with floats
    expect(lineTotalCents('0.10', 3)).toBe(30);
    expect(centsToString(lineTotalCents('19.99', 3))).toBe('59.97');
  });

  it('formats cents back to a decimal string', () => {
    expect(centsToString(5)).toBe('0.05');
    expect(centsToString(100000)).toBe('1000.00');
  });
});

describe('currency display', () => {
  it('shows rupees with Indian digit grouping, never dollars', () => {
    expect(formatMoney('45.20')).toContain('₹');
    expect(formatMoney('45.20')).not.toContain('$');
    expect(formatMoney('123456.5')).toBe('₹1,23,456.50');
    expect(formatCents(100000)).toBe('₹1,000.00');
  });
});

describe('permissions mirror the server matrix', () => {
  it('owner can do everything', () => {
    expect(can('OWNER', 'product:write')).toBe(true);
    expect(can('OWNER', 'dashboard:read')).toBe(true);
  });
  it('staff is limited', () => {
    expect(can('STAFF', 'order:create')).toBe(true);
    expect(can('STAFF', 'inventory:adjust')).toBe(true);
    expect(can('STAFF', 'product:write')).toBe(false);
    expect(can('STAFF', 'dashboard:read')).toBe(false);
    expect(can('STAFF', 'member:manage')).toBe(false);
    expect(can(null, 'product:read')).toBe(false);
  });
});

describe('ApiError', () => {
  it('maps field-level details for forms and keeps general details separate', () => {
    const error = new ApiError({
      status: 422,
      code: 'VALIDATION_ERROR',
      message: 'invalid',
      details: [
        { field: 'unit_price', message: 'too many decimals' },
        { field: 'unit_price', message: 'second message ignored' },
        { product_id: 'x', message: 'Out of stock' },
      ],
    });
    expect(error.fieldErrors).toEqual({ unit_price: 'too many decimals' });
    expect(error.generalDetails).toEqual([{ product_id: 'x', message: 'Out of stock' }]);
  });
});

describe('cleanParams', () => {
  it('drops empty values but keeps 0', () => {
    expect(cleanParams({ a: '', b: null, c: undefined, d: false, e: 0, f: 'x', g: true })).toEqual({ e: 0, f: 'x', g: true });
  });
});
