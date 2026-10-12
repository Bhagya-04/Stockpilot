# StockPilot — Frontend (React + Vite)

Single-page UI for the StockPilot API (`Stockpilot_BE`). Plain JavaScript (React 18, React Router 6, Vite 5) — no UI framework, no state library.

**Deployed app:** https://stockpilot-web-u8v0.onrender.com · **API:** https://stockpilot-api-6skh.onrender.com ([docs](https://stockpilot-api-6skh.onrender.com/docs))
**Demo login:** `admin@stockpilot.com` / `Admin@123` (Admin) · `staff@stockpilot.com` / `Staff@123` (Staff), or self-register.
The order/stock rules, roles and API are documented in the backend README ([`../Stockpilot_BE/README.md`](../Stockpilot_BE/README.md)).
> The API runs on a free Render instance that sleeps when idle: the first request after a pause (e.g. the first sign-in) can take about a minute.

## Screens

| Route | Who | What |
|---|---|---|
| `/login`, `/register` | public | sign in / create an account (optionally with a first workspace) |
| `/workspaces/new` | signed in | create a workspace |
| `/w/:workspaceId/dashboard` | Admin | metrics for a selectable UTC date range, orders by status, recent orders and stock changes |
| `/w/:workspaceId/products` | all | search, status/low-stock filters, sorting, pagination (filters live in the URL, so dashboard cards deep-link) |
| `/w/:workspaceId/products/new` | Admin | create a product (with opening stock) |
| `/w/:workspaceId/products/:id` | all (edit: Owner) | details, edit, deactivate/reactivate, **stock adjustment** (with confirmation) and per-product history with filters |
| `/w/:workspaceId/inventory` | all | workspace-wide stock history, filter by product / reason / date |
| `/w/:workspaceId/orders` | all | search by order number, status and date filters, sorting, pagination |
| `/w/:workspaceId/orders/new` | all | build a multi-item order (product search, quantities, live estimated total) |
| `/w/:workspaceId/orders/:id` | all | line items with price snapshots, timeline, **Confirm / Complete / Cancel** (with confirmation) |
| `/w/:workspaceId/members` | Admin | add staff by e-mail, change role, remove |

The current workspace is explicit in the URL and in the header switcher; users who belong to several workspaces switch there.

### UX details required by the brief
- Loading, empty, error (with retry and request reference) and success (toast) states on every data screen.
- Duplicate-submit protection: buttons disable while a request is in flight; order creation also sends an `Idempotency-Key`
  (regenerated whenever the order's contents change), so a retried request can never create two orders.
- Confirmation dialogs for stock adjustments, order placement/confirm/complete/cancel, deactivation and removing members.
- Validation errors appear next to the relevant field (client-side checks mirror the server; server `422` field errors are mapped back onto the form).
- Status is shown with **text + icon + colour**, never colour alone; low stock has a flag and a highlighted number.
- Responsive layout (the sidebar becomes a compact top block with scrollable links on phones, tables scroll inside their card, no horizontal page scroll at 375 px).
- Every list is paginated server-side, **10 rows per page** with numbered page buttons; amounts are shown in rupees (₹, `en-IN` grouping).
- The role the API calls `OWNER` is labelled **Admin** in the UI.
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

### Render (free Static Site) — how the live site is deployed
Created in the Render dashboard: **New → Static Site** → public repo `https://github.com/Bhagya-04/Stockpilot`, branch `main`,
**Root Directory** `Stockpilot_FE`, **Build Command** `npm ci && npm run build`, **Publish Directory** `dist`, environment variables
`VITE_API_BASE_URL=https://stockpilot-api-6skh.onrender.com/api/v1`, `NODE_VERSION=20`, `VITE_CURRENCY=INR`, `VITE_LOCALE=en-IN`. Then add the site's URL to the
backend's `CORS_ORIGINS`.

**Deep links / refresh:** a single-page app needs the host to serve `index.html` for every route. `npm run build` therefore also writes
`dist/404.html` (a copy of `index.html`, see `scripts/postbuild.mjs`), which Render serves for unknown paths. A dashboard rewrite rule
(`/*` → `/index.html`, action *Rewrite*) is the alternative. The repository-root `render.yaml` Blueprint describes the same service but has
not been run; the live site was created by hand. Static sites don't sleep, but the API they call does (see top).

## Known limitations
- The JWT is stored in `localStorage` (see backend README for the trade-off); the session ends on any `401`.
- The stock-history product filter lists the first 100 products by name.
- No automated browser/E2E tests; the UI was exercised manually against the seeded backend.
- A site deployed from a public Git URL doesn't rebuild on push; use Render's *Manual Deploy → Deploy latest commit*.

## AI-use disclosure (frontend)

**Tool used:** Claude Code (Anthropic's AI coding assistant), working from the written assessment brief. The full disclosure, covering
the whole project, is in [`../Stockpilot_BE/README.md`](../Stockpilot_BE/README.md#11-ai-use-disclosure); this is the frontend part.

**What it was used for**
- Generating the first version of the React app: routing, auth/workspace/toast/confirm contexts, the API client, all pages and components, and the stylesheet.
- Later changes requested by the author: the sidebar layout and colour scheme, a custom workspace dropdown, rupee formatting, 10-per-page pagination with numbered buttons, Admin/Staff labels, and the static-hosting fallback for page refreshes.
- Writing the frontend unit tests and this README.

**How it was verified**
- `npm test` (unit tests for the money/cents maths, the permission mirror and API error mapping) and `npm run build` were run after the changes.
- The UI was exercised in a browser against the running backend: sign-in, the multi-item order builder, cancelling an order, stock-adjustment validation, Staff vs Admin navigation, pagination, and a check of every screen at 375 px width for horizontal overflow.
- The deployed site was tested for page refresh (deep links), the link to the API, CORS and sign-in.

**What the author reviewed and changed:** the author tried the running UI and directed the design and wording changes listed above, chose the demo data shown, and tested the deployed site.

**Issues found and corrected**
- The workspace id wasn't visible to a parent layout component, so the layout was restructured so the route owns it.
- After signing in, users were returned to the page they had left; sign-in now always starts at the landing page (Dashboard for Admins).
- Refreshing a page on the static host returned "Not Found"; the build now also writes `dist/404.html` as a single-page-app fallback.
- Totals shown in the order form are only a client-side estimate in integer cents; the server's calculation is the authoritative one.
