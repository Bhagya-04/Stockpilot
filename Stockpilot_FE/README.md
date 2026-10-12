# StockPilot — Frontend (React + Vite)

Single-page UI for the StockPilot API (`Stockpilot_BE`). Plain JavaScript (React 18, React Router 6, Vite 5) — no UI framework, no state library.

**Deployed app:** `<ADD DEPLOYED URL>` · **API:** see the backend README.
Demo accounts and the order/stock rules are documented in the backend README.

## Screens

| Route | Who | What |
|---|---|---|
| `/login`, `/register` | public | sign in / create an account (optionally with a first workspace) |
| `/workspaces/new` | signed in | create a workspace |
| `/w/:workspaceId/dashboard` | Owner | metrics for a selectable UTC date range, orders by status, recent orders and stock changes |
| `/w/:workspaceId/products` | all | search, status/low-stock filters, sorting, pagination (filters live in the URL, so dashboard cards deep-link) |
| `/w/:workspaceId/products/new` | Owner | create a product (with opening stock) |
| `/w/:workspaceId/products/:id` | all (edit: Owner) | details, edit, deactivate/reactivate, **stock adjustment** (with confirmation) and per-product history with filters |
| `/w/:workspaceId/inventory` | all | workspace-wide stock history, filter by product / reason / date |
| `/w/:workspaceId/orders` | all | search by order number, status and date filters, sorting, pagination |
| `/w/:workspaceId/orders/new` | all | build a multi-item order (product search, quantities, live estimated total) |
| `/w/:workspaceId/orders/:id` | all | line items with price snapshots, timeline, **Confirm / Complete / Cancel** (with confirmation) |
| `/w/:workspaceId/members` | Owner | add staff by e-mail, change role, remove |

The current workspace is explicit in the URL and in the header switcher; users who belong to several workspaces switch there.

### UX details required by the brief
- Loading, empty, error (with retry and request reference) and success (toast) states on every data screen.
- Duplicate-submit protection: buttons disable while a request is in flight; order creation also sends an `Idempotency-Key`
  (regenerated whenever the order's contents change), so a retried request can never create two orders.
- Confirmation dialogs for stock adjustments, order placement/confirm/complete/cancel, deactivation and removing members.
- Validation errors appear next to the relevant field (client-side checks mirror the server; server `422` field errors are mapped back onto the form).
- Status is shown with **text + icon + colour**, never colour alone; low stock has a flag and a highlighted number.
- Responsive layout (collapsing navigation, tables scroll inside their card, no horizontal page scroll at 375 px).
- No dead controls: buttons shown are wired to API calls; role-restricted controls are hidden (the API enforces roles regardless).

### Money
Prices are exact decimal strings from the API. The UI does arithmetic only in **integer cents** (`src/utils/money.js`) and only for the
*estimated* total in the order form; the server computes the real total.

## Run locally

Requires Node 18+ and the backend running (default `http://localhost:8000`).

```bash
npm install
cp .env.example .env     # Windows: copy .env.example .env
npm run dev              # http://localhost:5173
```

| Variable | Default | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | API base URL including `/api/v1`; **baked in at build time** |
| `VITE_CURRENCY` | `INR` | ISO code (shows ₹), display formatting only |
| `VITE_LOCALE` | `en-IN` | number-format locale (Indian digit grouping) |

The backend must list this app's origin in its `CORS_ORIGINS` (e.g. `http://localhost:5173`).

## Tests and build

```bash
npm test          # vitest: money/cents maths, permission mirror, API error mapping
npm run build     # production bundle in dist/
```

The business rules (stock, totals, lifecycle, isolation, concurrency) are tested where they are enforced — in the backend suite.

## Deploy (static hosting)

`npm run build` and host `dist/` on any static host (Vercel, Netlify, Render Static, S3 + CloudFront…).

1. Set `VITE_API_BASE_URL=https://<your-api-host>/api/v1` in the host's build environment.
2. SPA fallback so deep links work: `vercel.json` (Vercel) and `public/_redirects` (Netlify/Cloudflare) are included.
3. Add the deployed frontend origin to the backend's `CORS_ORIGINS`.

### Render (free Static Site)
The repository-root `render.yaml` defines this app as a Render Static Site (root `Stockpilot_FE`, build `npm ci && npm run build`,
publish `dist`, SPA rewrite to `index.html`). In Render: **New → Blueprint** (or **New → Static Site** with root directory
`Stockpilot_FE`), pick the repo, and set `VITE_API_BASE_URL` to
`https://<your-api-service>.onrender.com/api/v1`. Static sites don't sleep. Remember to add the resulting site URL to the
backend's `CORS_ORIGINS`.

Not yet deployed from this repository — fill in the URL at the top once verified.

## Known limitations
- The JWT is stored in `localStorage` (see backend README for the trade-off); the session ends on any `401`.
- The stock-history product filter lists the first 100 products by name.
- No automated browser/E2E tests; the UI was exercised manually against the seeded backend.
