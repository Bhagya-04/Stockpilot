# StockPilot

Multi-workspace **inventory and order management** for small businesses.

| Folder | What | Stack |
|---|---|---|
| [`Stockpilot_BE`](Stockpilot_BE) | REST API, business rules, migrations, tests | Python · FastAPI · PostgreSQL · SQLAlchemy · Alembic |
| [`Stockpilot_FE`](Stockpilot_FE) | Web UI | React · JavaScript · Vite |

## Live demo
| | |
|---|---|
| App | https://stockpilot-web-u8v0.onrender.com |
| API / docs | https://stockpilot-api-6skh.onrender.com · [/docs](https://stockpilot-api-6skh.onrender.com/docs) · [/health](https://stockpilot-api-6skh.onrender.com/health) |
| Admin login | `admin@stockpilot.com` / `Admin@123` |
| Staff login | `staff@stockpilot.com` / `Staff@123` |
| Self-registration | "Create account" on the login page |

The API is on a free Render instance that **sleeps after ~15 minutes idle** — the first request can take about a minute. The free
demo database expires on **2026-11-11**.

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

## Submission checklist
- [x] Repository: https://github.com/Bhagya-04/Stockpilot
- [x] Deployed application: see *Live demo* above
- [x] Evaluator credentials / self-registration: see *Live demo*
- [x] README with setup, architecture, testing and decisions: `Stockpilot_BE/README.md` (+ `Stockpilot_FE/README.md`)
- [x] Migrations and demo-seed instructions: backend README §5 and §7
- [x] Automated tests and command: `cd Stockpilot_BE && pytest -q` (115 tests); `cd Stockpilot_FE && npm test`
- [x] Known limitations: backend README §9
- [x] Self-review against the brief: backend README §10
- [x] AI-use disclosure: backend README §11

## Deploy
The live demo runs on Render (API = Docker web service, UI = static site, database = free Render PostgreSQL). `render.yaml` (repo root)
describes the services as a Blueprint (not yet exercised). See the backend README, section "Deployment".

## Secrets
No secrets are committed. Copy `.env.example` to `.env` locally; production values live in the host's environment settings.
