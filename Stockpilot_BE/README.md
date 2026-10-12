# StockPilot — Backend (FastAPI + PostgreSQL)

StockPilot is a multi-workspace inventory and order management platform for small businesses.
This repository is the **API**; the React UI lives in the sibling `Stockpilot_FE` repository.

- **Workspaces** — each business has its own isolated products, stock history, orders, dashboard and team.
- **Products** — workspace-scoped catalogue with exact decimal prices, SKU uniqueness per workspace, low-stock thresholds, activate/deactivate.
- **Inventory ledger** — every stock change (manual adjustment, opening balance, order reservation, order cancellation) is an append-only row with who/why/when and the resulting stock.
- **Orders** — multi-item orders with server-calculated totals, immutable price/name/SKU snapshots, and a `Pending → Confirmed → Completed` lifecycle with cancellation.
- **Dashboard** — active products, low-stock count, orders by status, order value over a date range, recent orders and stock changes.
- **Auth & roles** — JWT login, `OWNER` / `STAFF` roles per workspace, enforced on the server for every request.

> **Deployed app:** `<ADD DEPLOYED FRONTEND URL>` · **API docs:** `<ADD DEPLOYED API URL>/docs` · **Health:** `<ADD DEPLOYED API URL>/health`
> **Demo login:** see [Demo access](#demo-access).
> Free hosting tiers sleep when idle — the first request after a pause can take 30–60 s.

---

## 1. Technology & architecture

| Layer | Choice |
|---|---|
| Language / framework | Python 3.12+ (developed on 3.14), FastAPI, Pydantic v2 |
| Database | PostgreSQL 13+ (uses `gen_random_uuid()`, row locks, partial unique indexes) |
| ORM / migrations | SQLAlchemy 2 (sync, psycopg 3), Alembic |
| Auth | bcrypt password hashes, signed JWT bearer tokens (HS256) |
| Tests | pytest + FastAPI `TestClient`, against a real PostgreSQL |

```
app/
  api/            HTTP only: routers, dependencies (auth + permission checks), error handlers
  services/       business rules + transaction boundaries (order lifecycle, stock changes, ...)
  repositories/   all SQL: queries, filters, pagination, row locking
  domain/         pure rules with no I/O (transitions, pricing, adjustment rules) - unit tested
  models/         SQLAlchemy tables and DB constraints
  schemas/        Pydantic request/response models and input validation
  core/           config (env), security (JWT/bcrypt), permissions matrix, errors, logging
alembic/          migrations (the schema is created ONLY by migrations)
scripts/seed.py   synthetic demo data
tests/            unit, API, isolation, concurrency and DB-constraint tests
```

Request path: `router → dependency (authenticate → workspace membership → permission) → service → repository → DB`.
Routers contain no business logic; services never touch HTTP; repositories contain no rules.

### Main data relationships

```mermaid
erDiagram
    USERS ||--o{ WORKSPACE_MEMBERSHIPS : "has"
    WORKSPACES ||--o{ WORKSPACE_MEMBERSHIPS : "has (role OWNER|STAFF)"
    WORKSPACES ||--o{ PRODUCTS : "owns"
    WORKSPACES ||--o{ ORDERS : "owns"
    PRODUCTS ||--o{ INVENTORY_ADJUSTMENTS : "ledger of stock changes"
    ORDERS ||--o{ ORDER_ITEMS : "snapshot lines"
    ORDERS ||--o{ INVENTORY_ADJUSTMENTS : "reserve / restore (optional)"
    PRODUCTS ||--o{ ORDER_ITEMS : "referenced by"
    USERS ||--o{ ORDERS : "created_by"
    USERS ||--o{ INVENTORY_ADJUSTMENTS : "performed by"
```

Integrity is enforced **in the database**, not only in code:

| Invariant | Mechanism |
|---|---|
| SKU unique per workspace (not globally) | `UNIQUE (workspace_id, sku)` |
| Stock never negative | `CHECK (stock_quantity >= 0)` (+ locked check in code) |
| Price / threshold non-negative, quantities positive | `CHECK` constraints; exact `NUMERIC(12,2)` money |
| `line_total = unit_price × quantity` | `CHECK` on `order_items` |
| A product can't be in another workspace's order or ledger | **composite foreign keys** `(product_id, workspace_id) → products(id, workspace_id)` on `order_items` and `inventory_adjustments`; same for `(order_id, workspace_id)` |
| No duplicate product in one order | `UNIQUE (order_id, product_id)` |
| Stock restored at most once per order line, even on retry/race | partial `UNIQUE (order_id, product_id, reason) WHERE order_id IS NOT NULL` on the ledger |
| Valid status / reason / role values | `CHECK ... IN (...)` |
| Retried order creation can't double-book | partial `UNIQUE (workspace_id, idempotency_key)` |
| Ledger never records a negative result or a zero change | `CHECK resulting_stock >= 0`, `CHECK quantity_change <> 0` |

---

## 2. Roles and permissions

> The stored/API role value is `OWNER`; the UI and demo accounts call it **Admin**.

Defined once in [`app/core/permissions.py`](app/core/permissions.py) and enforced by an API dependency on every workspace route
(hiding UI buttons is cosmetic only).

| Action | Owner | Staff |
|---|:--:|:--:|
| View products, orders, stock history | ✅ | ✅ |
| Create / edit / deactivate products | ✅ | ❌ 403 |
| Record stock adjustments | ✅ | ✅ |
| Create orders; confirm / complete / cancel orders | ✅ | ✅ |
| View dashboard metrics | ✅ | ❌ 403 |
| View / add / change / remove team members | ✅ | ❌ 403 |

Interpretation notes: the brief lists the dashboard under Owner capabilities and not under Staff, so it is Owner-only here.
Stock history is visible to Staff because they record adjustments and need to see them. Both are one-line changes in the matrix.

**How staff membership is created (no email invitations):** the staff member registers normally, then an Owner adds them by e-mail
in the *Team* page (`POST /workspaces/{id}/members`). A user can belong to several workspaces with a different role in each.
A workspace must always keep at least one Owner.

### Authentication and isolation rules
- Identity comes **only** from the verified bearer token; any `user_id` in a body is ignored (tested).
- Every workspace route takes `workspace_id` from the URL, checks the caller's membership, **then** the role's permission.
- A non-member gets **404 `WORKSPACE_NOT_FOUND`** — byte-identical to a workspace that doesn't exist — so ids can't be probed.
  A member lacking permission gets **403**.
- Every repository query filters by `workspace_id` as well as the object id; a product/order id from another workspace is simply "not found".
- Roles are read from the database on each request, so removing a member takes effect immediately.
- Secrets live only in environment variables. `.env` is git-ignored; only `.env.example` (placeholders) is committed.

---

## 3. Order lifecycle and stock strategy

**Strategy chosen: _reserve stock at order creation_.**

```
          create (stock deducted, ledger: ORDER_RESERVED)
             |
          PENDING ──confirm──▶ CONFIRMED ──complete──▶ COMPLETED   (terminal, deduction kept)
             │                    │
             └──────cancel────────┴──▶ CANCELLED                    (terminal, stock restored once,
                                                                     ledger: ORDER_CANCELLED)
```

| Transition | Allowed | Stock effect |
|---|---|---|
| (new) → PENDING | create | deduct every line (`ORDER_RESERVED`) |
| PENDING → CONFIRMED | yes | none (already reserved) |
| CONFIRMED → COMPLETED | yes | none (deduction retained) |
| PENDING → CANCELLED, CONFIRMED → CANCELLED | yes | restore every line, **exactly once** (`ORDER_CANCELLED`) |
| anything else (e.g. PENDING → COMPLETED, COMPLETED/CANCELLED → anything) | **409 `INVALID_TRANSITION`** | none |

Order rules:
- The client sends only `product_id` + `quantity`. Unit prices, line totals and the order total are computed on the server from
  stored prices using `Decimal`. Any price/total/status/creator sent by the client is ignored.
- Each line stores a snapshot of product name, SKU and unit price, so later catalogue edits never change history.
- Duplicate lines for the same product are **merged** (quantities summed) before validation and stock changes.
- Inactive products, unknown/foreign products and insufficient stock reject the **whole** order; the response lists every problem.
- Optional `Idempotency-Key` header: retrying the same create request returns the original order (200) instead of creating a second one.
- Order lines cannot be edited after creation (cancel and re-create instead) — see limitations.

### Transactions, locking and concurrency
All writes that span several rows run in one transaction through `unit_of_work()` — commit on success, rollback on **any** exception.
Nothing is committed until the end of the service call, so a failure on line 3 leaves no trace of lines 1–2.

- **Create order:** products are locked with `SELECT … FOR UPDATE` in primary-key order, then validated *under the lock*, then deducted.
  Two requests for the last unit serialise on the lock; the second sees stock 0 and is rejected. Sorted lock order prevents deadlocks between
  multi-item orders that list products in opposite order (tested).
- **Cancel / confirm / complete:** the order row is locked first, so a retried or concurrent request waits, then sees the new status and gets 409.
  Stock is restored only inside the single legal `→ CANCELLED` transition. The partial unique index on the ledger is a database-level
  backstop that would make a double restore impossible even if code changed.
- **Stock adjustments:** the product row is locked; the new level is computed and validated; the stock update and ledger row are written together.
- `CHECK (stock_quantity >= 0)` is the last line of defence if any code path were wrong.
- The ledger and current stock cannot diverge: `apply_stock_change()` in `inventory_service.py` is the **only** function that mutates stock and it always writes the ledger row.
  The test-suite verifies `current stock == sum(ledger)` and each row's `resulting_stock` is the running total.

---

## 4. Dashboard metric definitions

All dashboard values come from the database. Date range = **UTC calendar days, inclusive on both ends**; default = last 30 days including today.

| Metric | Definition |
|---|---|
| `total_active_products` | products with `is_active = true` |
| `low_stock_products` | **active** products with `stock_quantity <= low_stock_threshold` (same definition as the products-list `low_stock` filter and `is_low_stock` flag) |
| `order_counts_by_status` | orders **created in the range**, per status (all four statuses always present, zero-filled) |
| `order_value` | sum of `total_amount` of orders created in the range with status Pending + Confirmed + Completed — **cancelled orders excluded** (their stock was returned) |
| `completed_order_value` | same, restricted to Completed orders |
| `recent_orders` / `recent_adjustments` | latest 5 orders / 10 ledger rows in the workspace, independent of the range |

**Timezone convention:** all timestamps are stored as `timestamptz` (UTC) and returned as ISO-8601 UTC. `date_from` / `date_to` filters
are `YYYY-MM-DD` and are interpreted as UTC days (`created_at >= date_from 00:00Z` and `< date_to + 1 day 00:00Z`). The UI labels date filters "(UTC)".

---

## 5. Run locally

Prerequisites: Python 3.12+, PostgreSQL 13+ running locally.

```bash
# 1. databases (names are examples)
createdb stockpilot
createdb stockpilot_test          # disposable: the test-suite wipes it

# 2. install
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt

# 3. configure (never commit .env)
copy .env.example .env            # macOS/Linux: cp .env.example .env
#    edit .env: DATABASE_URL, TEST_DATABASE_URL, SECRET_KEY, CORS_ORIGINS

# 4. create the schema from migrations
alembic upgrade head

# 5. (optional) load synthetic demo data
python -m scripts.seed

# 6. start the API  ->  http://localhost:8000  (interactive docs at /docs)
uvicorn app.main:app --reload
```

### Environment variables

| Name | Required | Example / notes |
|---|:--:|---|
| `DATABASE_URL` | ✅ | `postgresql+psycopg://USER:PASSWORD@localhost:5432/stockpilot` (`postgres://…` from hosts is auto-converted) |
| `SECRET_KEY` | ✅ | ≥ 32 random chars: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CORS_ORIGINS` | ✅ in prod | comma-separated allowed browser origins, e.g. `https://your-frontend.example` |
| `ENVIRONMENT` | | `development` (default) / `production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | default `720` |
| `LOG_LEVEL` | | default `INFO` |
| `TEST_DATABASE_URL` | tests only | must point to a **different** DB whose name contains `test` |

The app refuses to start if `DATABASE_URL`/`SECRET_KEY` are missing or the key is shorter than 32 characters.

### Run the tests

```bash
pytest -q              # everything: unit + API + isolation + concurrency + DB constraints
pytest tests/test_unit_rules.py   # pure unit tests only, no database needed
```

`TEST_DATABASE_URL` must be set (env var or `.env`). At the start of each run the test schema is **dropped and rebuilt from the Alembic
migrations** (so a fresh database from this repo is proven to work), and tables are truncated between tests. DB-backed tests are skipped,
with a message, if `TEST_DATABASE_URL` is not set.

Coverage of the required scenarios:

| Required test | File |
|---|---|
| SKU uniqueness (same workspace rejected, other workspace allowed) | `test_products.py`, `test_db_constraints.py` |
| Stock boundaries / never negative | `test_inventory.py`, `test_db_constraints.py` |
| Server-calculated totals, client totals ignored | `test_orders.py`, `test_unit_rules.py` |
| Insufficient stock | `test_orders.py` |
| Multi-item atomicity (no partial order or stock change) | `test_orders.py`, `test_isolation.py` |
| Cancellation restores once, not twice | `test_orders.py`, `test_concurrency.py`, `test_db_constraints.py` |
| Invalid state transitions | `test_orders.py`, `test_unit_rules.py` |
| Price snapshots | `test_orders.py` |
| Workspace isolation by ID tampering | `test_isolation.py` |
| Concurrency (competing orders, double cancel, deadlock ordering, idempotency) | `test_concurrency.py` |
| Migrations match models | `test_db_constraints.py::test_models_and_migrations_are_in_sync` |

I also verified the concurrency tests are meaningful by temporarily removing the `FOR UPDATE` locks: 4 of them then fail (overselling).

---

## 6. API

Base path `/api/v1`. Interactive, always-current docs: **`/docs`** (Swagger) and `/redoc`. Authenticate with `Authorization: Bearer <token>`.
`{ws}` = workspace id.

| Method & path | Role | Purpose |
|---|---|---|
| `POST /auth/register` · `POST /auth/login` · `GET /auth/me` | public / any | account + token |
| `GET /workspaces` · `POST /workspaces` | any | my workspaces (with my role) · create one (I become Owner) |
| `GET/POST /workspaces/{ws}/members` · `PATCH/DELETE …/members/{user_id}` | Owner | team management |
| `GET/POST /workspaces/{ws}/products` | read: any · write: Owner | list (`q, sku, active, low_stock, sort_by, sort_dir, page, page_size`) · create |
| `GET/PATCH /workspaces/{ws}/products/{id}` | read: any · write: Owner | details · edit / deactivate (`{"is_active": false}`); stock is **not** editable here |
| `POST/GET /workspaces/{ws}/products/{id}/adjustments` | any | record a stock adjustment · that product's history |
| `GET /workspaces/{ws}/inventory/adjustments` | any | workspace stock history (`product_id, reason, date_from, date_to, page`) |
| `GET/POST /workspaces/{ws}/orders` | any | list (`status, q, date_from, date_to, sort_by, sort_dir, page`) · create (`Idempotency-Key` optional) |
| `GET /workspaces/{ws}/orders/{id}` | any | detail with line items |
| `POST /workspaces/{ws}/orders/{id}/confirm` · `/complete` · `/cancel` | any | lifecycle transitions |
| `GET /workspaces/{ws}/dashboard` | Owner | metrics (`date_from`, `date_to`) |
| `GET /health` | public | liveness + DB check (no secrets) |

Lists return `{ "items": [...], "total": n, "page": 1, "page_size": 20, "pages": k }`; `page_size` is capped at 100.

**Errors** always use one envelope; stack traces and internals are never returned (they are logged server-side with the same `request_id`):

```json
{ "error": { "code": "INSUFFICIENT_STOCK", "message": "…", "details": [ { "product_id": "…", "available": 3, "requested": 4 } ], "request_id": "…" } }
```

Status codes: `401` not authenticated · `403` role lacks permission · `404` not found / not a member · `409` state conflict
(`DUPLICATE_SKU`, `INSUFFICIENT_STOCK`, `INVALID_TRANSITION`, `EMAIL_TAKEN`, `LAST_OWNER`, …) · `422` invalid input.

Example requests:

```bash
# register an owner with a first workspace
curl -X POST $API/api/v1/auth/register -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"a-long-password","full_name":"Me","workspace_name":"My Shop"}'

# create a product with opening stock
curl -X POST $API/api/v1/workspaces/$WS/products -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"name":"Wireless Mouse","sku":"MOU-001","unit_price":"599.00","stock_quantity":40,"low_stock_threshold":10}'

# place a two-line order (safe to retry with the same key)
curl -X POST $API/api/v1/workspaces/$WS/orders -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -H 'Idempotency-Key: 3f2b6c1e-demo-0001' \
  -d '{"items":[{"product_id":"<id1>","quantity":2},{"product_id":"<id2>","quantity":1}]}'

# cancel it (stock is restored once; a second call returns 409)
curl -X POST $API/api/v1/workspaces/$WS/orders/$ORDER/cancel -H "authorization: Bearer $TOKEN"
```

Logging: one line per request (`request_id method path -> status ms`); query strings, bodies, tokens and passwords are never logged;
SQL bound parameters are hidden (`hide_parameters=True`). Responses carry `X-Request-ID` for correlating a user report with the logs.

---

## 7. Demo access

Seed synthetic data with `python -m scripts.seed` (safe to re-run; it does nothing if the demo owner already exists). It creates two
**unrelated** workspaces so isolation can be demonstrated, with orders in every status.

| Role | Email | Password | Workspace |
|---|---|---|---|
| **Admin** (owner, full access) | `admin@stockpilot.com` | `Admin@123` | Acme Electronics |
| **Staff** (limited) | `staff@stockpilot.com` | `Staff@123` | Acme Electronics |
| **Admin 2** (owner of a separate business) | `admin2@stockpilot.com` | `Admin2@123` | Rival Traders |

These are public, demo-only credentials for synthetic accounts (defined in `scripts/seed.py`) — **do not seed a database that holds
real data.** A database seeded by an earlier version (with `owner@/staff@/rival@demo-stockpilot.com`) is upgraded in place by
re-running `python -m scripts.seed`.
Alternatively, anyone can self-register on the login page.

---

## 8. Deployment

Any host with PostgreSQL works. The repo includes a `Dockerfile` (runs `alembic upgrade head` then uvicorn) and a Render blueprint
(a root-level `render.yaml` for both services; use a free Neon database for PostgreSQL). **Those two files have not been deployed from this
repository yet** — treat them as a starting point and fill in the deployed URLs above once you have verified them.

Checklist:
1. Provision PostgreSQL; set `DATABASE_URL`.
2. Set `SECRET_KEY` (random, ≥ 32 chars), `ENVIRONMENT=production`.
3. Set `CORS_ORIGINS` to the exact deployed frontend origin (scheme + host, no trailing slash).
4. Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
5. Seed demo data once if wanted: `python -m scripts.seed`.
6. Point the frontend's `VITE_API_BASE_URL` at `https://<api-host>/api/v1`.

Auth uses bearer tokens (no cookies), so no cookie/SameSite configuration is needed across domains — only CORS.

---

## 9. Known limitations and trade-offs

- **Token storage:** the SPA keeps the JWT in `localStorage` (simple, works across domains) — vulnerable to token theft if an XSS bug existed; no refresh tokens or server-side revocation (tokens expire after 12 h; removing a user from a workspace is immediate, disabling an account is checked on every request).
- **No rate limiting / lockout** on login; no e-mail verification or password reset; no invitations (owners add existing users by e-mail, which reveals whether an address is registered — only to owners).
- **Orders can't be edited** after creation (only status transitions); to change items, cancel and re-create.
- **Returns after completion** are not modelled; a completed order is final. Customers' returned goods can be restocked with a manual `RETURNED` adjustment.
- **Single currency**, no tax/discounts/shipping.
- Products are never hard-deleted (only deactivated) so history stays intact.
- Search is `ILIKE` substring matching — fine for thousands of products; use `pg_trgm` indexes for much larger catalogues.
- The stock-history product filter in the UI loads the first 100 products by name.
- Dashboard "order value" counts orders by *creation* date, not completion date.
- Sync SQLAlchemy in a thread pool (adequate for this scale; no background jobs).
- `render.yaml` / `Dockerfile` are untested against a real deployment.
