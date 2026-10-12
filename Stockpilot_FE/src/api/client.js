// Thin fetch wrapper around the StockPilot API.
// Errors are normalised into ApiError (status, code, message, details, requestId).

import { cleanParams } from '../utils/format.js';

const BASE_URL = (import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '');
const TOKEN_KEY = 'stockpilot.token';

let token = null;
try {
  token = localStorage.getItem(TOKEN_KEY);
} catch {
  /* storage unavailable (private mode) - session just won't persist */
}
let onUnauthorized = () => {};

export function getToken() {
  return token;
}

export function setToken(value) {
  token = value;
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

export class ApiError extends Error {
  constructor({ status, code, message, details = [], requestId = null }) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  /** { fieldName: message } for validation-style errors, so forms can show them next to inputs. */
  get fieldErrors() {
    const map = {};
    for (const d of this.details) {
      if (d.field && d.message && !map[d.field]) map[d.field] = d.message;
    }
    return map;
  }

  /** Details that are not tied to a form field (e.g. per-product order problems). */
  get generalDetails() {
    return this.details.filter((d) => !d.field && d.message);
  }
}

async function request(method, path, { params, body, headers = {}, auth = true } = {}) {
  const query = params ? new URLSearchParams(cleanParams(params)).toString() : '';
  const url = `${BASE_URL}${path}${query ? `?${query}` : ''}`;
  const finalHeaders = { Accept: 'application/json', ...headers };
  if (body !== undefined) finalHeaders['Content-Type'] = 'application/json';
  if (auth && token) finalHeaders.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(url, {
      method,
      headers: finalHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError({
      status: 0,
      code: 'NETWORK_ERROR',
      message: 'Cannot reach the server. Check your connection and try again.',
    });
  }

  if (response.status === 204) return null;

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    /* non-JSON body */
  }

  if (!response.ok) {
    const err = payload?.error;
    const error = new ApiError({
      status: response.status,
      code: err?.code || 'HTTP_ERROR',
      message: err?.message || `Request failed (${response.status})`,
      details: err?.details || [],
      requestId: err?.request_id || null,
    });
    if (response.status === 401 && auth && error.code !== 'INVALID_CREDENTIALS') onUnauthorized();
    throw error;
  }
  return payload;
}

const ws = (id) => `/workspaces/${id}`;

export const api = {
  auth: {
    login: (body) => request('POST', '/auth/login', { body, auth: false }),
    register: (body) => request('POST', '/auth/register', { body, auth: false }),
    me: () => request('GET', '/auth/me'),
  },
  workspaces: {
    list: () => request('GET', '/workspaces'),
    create: (name) => request('POST', '/workspaces', { body: { name } }),
    members: (id) => request('GET', `${ws(id)}/members`),
    addMember: (id, body) => request('POST', `${ws(id)}/members`, { body }),
    changeRole: (id, userId, role) => request('PATCH', `${ws(id)}/members/${userId}`, { body: { role } }),
    removeMember: (id, userId) => request('DELETE', `${ws(id)}/members/${userId}`),
  },
  products: {
    list: (id, params) => request('GET', `${ws(id)}/products`, { params }),
    get: (id, productId) => request('GET', `${ws(id)}/products/${productId}`),
    create: (id, body) => request('POST', `${ws(id)}/products`, { body }),
    update: (id, productId, body) => request('PATCH', `${ws(id)}/products/${productId}`, { body }),
    adjust: (id, productId, body) => request('POST', `${ws(id)}/products/${productId}/adjustments`, { body }),
    history: (id, productId, params) => request('GET', `${ws(id)}/products/${productId}/adjustments`, { params }),
  },
  inventory: {
    history: (id, params) => request('GET', `${ws(id)}/inventory/adjustments`, { params }),
  },
  orders: {
    list: (id, params) => request('GET', `${ws(id)}/orders`, { params }),
    get: (id, orderId) => request('GET', `${ws(id)}/orders/${orderId}`),
    create: (id, body, idempotencyKey) =>
      request('POST', `${ws(id)}/orders`, { body, headers: { 'Idempotency-Key': idempotencyKey } }),
    transition: (id, orderId, action) => request('POST', `${ws(id)}/orders/${orderId}/${action}`),
  },
  dashboard: {
    get: (id, params) => request('GET', `${ws(id)}/dashboard`, { params }),
  },
};
