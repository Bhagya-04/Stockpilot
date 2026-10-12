"""Dashboard metrics come from persisted data and follow the documented definitions."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text


def dashboard(client, user, **params):
    response = client.get(f"/api/v1/workspaces/{user['workspace_id']}/dashboard", params=params, headers=user["headers"])
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_workspace_returns_zeroes_not_errors(client, owner):
    data = dashboard(client, owner)
    assert data["total_active_products"] == 0
    assert data["low_stock_products"] == 0
    assert data["order_counts_by_status"] == {"PENDING": 0, "CONFIRMED": 0, "COMPLETED": 0, "CANCELLED": 0}
    assert Decimal(data["order_value"]) == 0 and Decimal(data["completed_order_value"]) == 0
    assert data["recent_orders"] == [] and data["recent_adjustments"] == []
    today = date.today()
    assert data["range"]["date_to"] >= str(today - timedelta(days=1))  # defaults to a 30-day UTC window
    assert (date.fromisoformat(data["range"]["date_to"]) - date.fromisoformat(data["range"]["date_from"])).days == 29


def test_metrics_follow_the_documented_definitions(api, client, owner):
    ws = owner["workspace_id"]
    plenty = api.product(owner, ws, price="10.00", stock=100, threshold=5)
    low = api.product(owner, ws, price="20.00", stock=10, threshold=10)  # == threshold counts as low
    api.product(owner, ws, stock=0, threshold=3, is_active=False)  # inactive: neither active nor low

    pending = api.order(owner, ws, [(plenty["id"], 1)])  # 10.00
    confirmed = api.order(owner, ws, [(plenty["id"], 2)])  # 20.00
    completed = api.order(owner, ws, [(low["id"], 1)])  # 20.00
    cancelled = api.order(owner, ws, [(plenty["id"], 5)])  # 50.00 - excluded from value
    api.order_action(owner, ws, confirmed["id"], "confirm")
    api.order_action(owner, ws, completed["id"], "confirm")
    api.order_action(owner, ws, completed["id"], "complete")
    api.order_action(owner, ws, cancelled["id"], "cancel")

    data = dashboard(client, owner)
    assert data["total_active_products"] == 2
    assert data["low_stock_products"] == 1  # `low` has 9 left (<= 10); plenty has 92 (> 5)
    assert data["order_counts_by_status"] == {"PENDING": 1, "CONFIRMED": 1, "COMPLETED": 1, "CANCELLED": 1}
    assert Decimal(data["order_value"]) == Decimal("50.00")  # 10 + 20 + 20, cancelled excluded
    assert Decimal(data["completed_order_value"]) == Decimal("20.00")
    assert [o["id"] for o in data["recent_orders"]][0] == cancelled["id"]  # newest first
    assert len(data["recent_orders"]) == 4
    assert data["recent_adjustments"][0]["reason"] == "ORDER_CANCELLED"
    assert pending["status"] == "PENDING"


def test_dashboard_numbers_match_the_product_list_filters(api, client, owner):
    ws = owner["workspace_id"]
    api.product(owner, ws, stock=1, threshold=1)
    api.product(owner, ws, stock=9, threshold=1)
    low_list = client.get(f"/api/v1/workspaces/{ws}/products", params={"low_stock": "true"}, headers=owner["headers"]).json()
    assert dashboard(client, owner)["low_stock_products"] == low_list["total"] == 1


def test_date_range_selects_orders_by_creation_date(api, client, db, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, price="10.00", stock=100)
    old = api.order(owner, ws, [(product["id"], 3)])
    recent = api.order(owner, ws, [(product["id"], 1)])
    # backdate one order to 10 January 2020 (UTC) to exercise the range filter
    db.execute(text("UPDATE orders SET created_at = '2020-01-10 23:30:00+00' WHERE id = :id"), {"id": old["id"]})
    db.commit()

    default_range = dashboard(client, owner)
    assert Decimal(default_range["order_value"]) == Decimal("10.00")
    assert default_range["order_counts_by_status"]["PENDING"] == 1

    january = dashboard(client, owner, date_from="2020-01-01", date_to="2020-01-31")
    assert Decimal(january["order_value"]) == Decimal("30.00")
    assert january["range"] == {"date_from": "2020-01-01", "date_to": "2020-01-31"}
    # inclusive end date, UTC day boundaries: 23:30 on the 10th belongs to the 10th
    assert Decimal(dashboard(client, owner, date_from="2020-01-10", date_to="2020-01-10")["order_value"]) == Decimal("30.00")
    assert Decimal(dashboard(client, owner, date_from="2020-01-11", date_to="2020-01-12")["order_value"]) == Decimal("0.00")
    assert recent["status"] == "PENDING"

    assert client.get(
        f"/api/v1/workspaces/{ws}/dashboard", params={"date_from": "2020-02-01", "date_to": "2020-01-01"}, headers=owner["headers"]
    ).status_code == 422


def test_dashboard_only_counts_its_own_workspace(api, client, owner, other_owner):
    api.product(other_owner, other_owner["workspace_id"], stock=1)
    p = api.product(other_owner, other_owner["workspace_id"], stock=5)
    api.order(other_owner, other_owner["workspace_id"], [(p["id"], 1)])
    data = dashboard(client, owner)
    assert data["total_active_products"] == 0 and data["recent_orders"] == []
