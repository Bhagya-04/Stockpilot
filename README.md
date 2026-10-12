# StockPilot

Multi-workspace **inventory and order management** for small businesses.

| Folder | What | Stack |
|---|---|---|
| [`Stockpilot_BE`](Stockpilot_BE) | REST API, business rules, migrations, tests | Python · FastAPI · PostgreSQL · SQLAlchemy · Alembic |
| [`Stockpilot_FE`](Stockpilot_FE) | Web UI | React · JavaScript · Vite |

**Start here:** the backend README ([`Stockpilot_BE/README.md`](Stockpilot_BE/README.md)) documents the architecture, roles and
permissions, order lifecycle and stock strategy, dashboard metrics, API, tests and known limitations.
The frontend README ([`Stockpilot_FE/README.md`](Stockpilot_FE/README.md)) covers the screens and how to run/build the UI.

## Features
- Separate business **workspaces**; every request is authorised against workspace membership (Admin / Staff roles enforced on the server).
- **Products** with exact-decimal prices, per-workspace unique SKUs, low-stock thresholds, search / filters / pagination.
- **Inventory ledger**: every stock change is audited (who, why, when, resulting stock).
- **Orders** with multiple line items, server-calculated totals, price snapshots and a Pending → Confirmed → Completed lifecycle with cancellation
  (stock reserved at creation, restored exactly once on cancel). Safe under concurrent requests (row locks + DB constraints).
- **Dashboard** with metrics over a selectable date range.

## Quick start (local)
```bash
# backend  (needs Python 3.12+, PostgreSQL)
cd Stockpilot_BE
python -m venv .venv && .venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env                                  # then edit DATABASE_URL, SECRET_KEY ...
alembic upgrade head
python -m scripts.seed                                  # synthetic demo data
uvicorn app.main:app --reload

# frontend (needs Node 18+) - in a second terminal
cd Stockpilot_FE
npm install
npm run dev                                             # http://localhost:5173
```
Demo logins (synthetic, public): `admin@stockpilot.com` / `Admin@123` · `staff@stockpilot.com` / `Staff@123`.

## Tests
```bash
cd Stockpilot_BE && pytest -q        # 115 tests incl. concurrency and DB-constraint tests (needs TEST_DATABASE_URL)
cd Stockpilot_FE && npm test         # frontend unit tests
```

## Deploy
`render.yaml` (repo root) describes both services for Render (API as a Docker web service, UI as a static site); use a free
[Neon](https://neon.com) PostgreSQL for the database. See the backend README, section "Deployment". Free tiers sleep when idle —
the first request after a pause can take about a minute.

## Secrets
No secrets are committed. Copy `.env.example` to `.env` locally; production values live in the host's environment settings.
