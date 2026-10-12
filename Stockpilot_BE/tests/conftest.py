"""Test configuration.

Database-backed tests need a real PostgreSQL (row locks / constraints are the point of the tests).
Point TEST_DATABASE_URL (env var or .env) at a DISPOSABLE database: the schema is dropped and rebuilt
from the Alembic migrations at the start of every run, and tables are truncated between tests.
"""

import os
import secrets
import uuid
from pathlib import Path

import pytest
from dotenv import dotenv_values

_ROOT = Path(__file__).resolve().parents[1]
_dotenv = dotenv_values(_ROOT / ".env")

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL") or _dotenv.get("TEST_DATABASE_URL")

# These must be set BEFORE the application (and therefore Settings) is imported.
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(48)
os.environ["LOG_LEVEL"] = "WARNING"
if _TEST_DB_URL:
    os.environ["DATABASE_URL"] = _TEST_DB_URL
else:  # lets pure unit tests import the app code; DB tests are skipped below
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.db.base import Base  # noqa: E402

DB_AVAILABLE = bool(_TEST_DB_URL)
PASSWORD = "Sup3r-secret-pw"


def pytest_collection_modifyitems(config, items):
    if DB_AVAILABLE:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL is not set (see README)")
    for item in items:
        if {"client", "db", "api", "_database"} & set(item.fixturenames):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def _database():
    """Fresh schema built from the real migrations (also proves a clean DB can be bootstrapped)."""
    assert _TEST_DB_URL
    db_name = _TEST_DB_URL.rsplit("/", 1)[-1].split("?")[0]
    if "test" not in db_name.lower():
        pytest.exit(f"Refusing to wipe database '{db_name}': TEST_DATABASE_URL must point at a database whose name contains 'test'.")
    engine = create_engine(_TEST_DB_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    command.upgrade(cfg, "head")
    yield _TEST_DB_URL


@pytest.fixture
def db(_database):
    """A SQLAlchemy session on the test DB, with all tables emptied first."""
    from app.db.session import get_engine, get_sessionmaker

    table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with get_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db):
    from app.main import app

    return TestClient(app)


class Api:
    """Small helper around the test client so tests read like scenarios."""

    def __init__(self, client: TestClient):
        self.client = client
        self._counter = 0

    # -- users / workspaces ------------------------------------------------------------------
    def register(self, email: str, workspace_name: str | None = None, name: str = "Test User") -> dict:
        payload = {"email": email, "password": PASSWORD, "full_name": name}
        if workspace_name:
            payload["workspace_name"] = workspace_name
        response = self.client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201, response.text
        data = response.json()
        return {"token": data["access_token"], "user": data["user"], "headers": {"Authorization": f"Bearer {data['access_token']}"}}

    def workspaces(self, headers: dict) -> list[dict]:
        response = self.client.get("/api/v1/workspaces", headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    def add_staff(self, owner: dict, workspace_id: str, staff_email: str) -> None:
        response = self.client.post(
            f"/api/v1/workspaces/{workspace_id}/members",
            json={"email": staff_email, "role": "STAFF"},
            headers=owner["headers"],
        )
        assert response.status_code == 201, response.text

    # -- products ----------------------------------------------------------------------------
    def product(self, user: dict, workspace_id: str, sku: str | None = None, price: str = "10.00", stock: int = 0, threshold: int = 0, **extra) -> dict:
        self._counter += 1
        payload = {
            "name": extra.pop("name", f"Product {self._counter}"),
            "sku": sku or f"SKU-{self._counter}",
            "unit_price": price,
            "stock_quantity": stock,
            "low_stock_threshold": threshold,
            **extra,
        }
        response = self.client.post(f"/api/v1/workspaces/{workspace_id}/products", json=payload, headers=user["headers"])
        assert response.status_code == 201, response.text
        return response.json()

    # -- orders ------------------------------------------------------------------------------
    def order(
        self,
        user: dict,
        workspace_id: str,
        items: list[tuple[str, int]],
        expect: int = 201,
        idempotency_key: str | None = None,
        **extra,
    ):
        payload = {"items": [{"product_id": pid, "quantity": qty} for pid, qty in items], **extra}
        headers = dict(user["headers"])
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        response = self.client.post(f"/api/v1/workspaces/{workspace_id}/orders", json=payload, headers=headers)
        assert response.status_code == expect, response.text
        return response.json()

    def order_action(self, user: dict, workspace_id: str, order_id: str, action: str):
        return self.client.post(f"/api/v1/workspaces/{workspace_id}/orders/{order_id}/{action}", headers=user["headers"])

    def get_product(self, user: dict, workspace_id: str, product_id: str) -> dict:
        response = self.client.get(f"/api/v1/workspaces/{workspace_id}/products/{product_id}", headers=user["headers"])
        assert response.status_code == 200, response.text
        return response.json()

    def stock(self, user: dict, workspace_id: str, product_id: str) -> int:
        return self.get_product(user, workspace_id, product_id)["stock_quantity"]


@pytest.fixture
def api(client) -> Api:
    return Api(client)


@pytest.fixture
def owner(api):
    """An owner with a workspace of their own: dict(token, user, headers, workspace_id)."""
    user = api.register("owner@example.com", workspace_name="Acme Hardware", name="Admin")
    user["workspace_id"] = api.workspaces(user["headers"])[0]["id"]
    return user


@pytest.fixture
def staff(api, owner):
    user = api.register("staff@example.com", name="Staff")
    api.add_staff(owner, owner["workspace_id"], "staff@example.com")
    user["workspace_id"] = owner["workspace_id"]
    return user


@pytest.fixture
def other_owner(api):
    """Owner of a completely separate workspace (used for isolation tests)."""
    user = api.register("other@example.com", workspace_name="Rival Traders", name="Admin 2")
    user["workspace_id"] = api.workspaces(user["headers"])[0]["id"]
    return user


def new_uuid() -> str:
    return str(uuid.uuid4())
