"""Inventory adjustments: stock boundaries and the audit ledger."""

from datetime import date, timedelta


def adjust(client, user, ws, product_id, change, reason="CORRECTION", note=None):
    return client.post(
        f"/api/v1/workspaces/{ws}/products/{product_id}/adjustments",
        json={"quantity_change": change, "reason": reason, "note": note},
        headers=user["headers"],
    )


def test_adjustment_updates_stock_and_records_history(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)

    received = adjust(client, owner, ws, product["id"], 5, "RECEIVED", "PO-1")
    assert received.status_code == 201
    body = received.json()
    assert body["product"]["stock_quantity"] == 15
    entry = body["adjustment"]
    assert (entry["quantity_change"], entry["resulting_stock"], entry["reason"], entry["note"]) == (5, 15, "RECEIVED", "PO-1")
    assert entry["user"]["id"] == owner["user"]["id"]
    assert entry["created_at"]

    damaged = adjust(client, owner, ws, product["id"], -3, "DAMAGED")
    assert damaged.json()["adjustment"]["resulting_stock"] == 12
    assert api.stock(owner, ws, product["id"]) == 12


def test_stock_can_never_go_negative(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=4)
    response = adjust(client, owner, ws, product["id"], -5, "CORRECTION")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INSUFFICIENT_STOCK"
    assert error["details"][0]["available"] == 4
    assert api.stock(owner, ws, product["id"]) == 4
    # ...and the rejected attempt left no audit row behind (only the opening balance exists)
    history = client.get(f"/api/v1/workspaces/{ws}/products/{product['id']}/adjustments", headers=owner["headers"]).json()
    assert history["total"] == 1

    exact = adjust(client, owner, ws, product["id"], -4, "CORRECTION")  # exactly to zero is fine
    assert exact.status_code == 201 and exact.json()["product"]["stock_quantity"] == 0


def test_invalid_adjustments_are_rejected_with_clear_errors(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    cases = [
        (0, "CORRECTION", None),  # no-op
        (-2, "RECEIVED", None),  # receiving must add stock
        (2, "DAMAGED", None),  # damage must remove stock
        (3, "OTHER", None),  # OTHER needs a note
        (1, "ORDER_RESERVED", None),  # system-only reason
        (1, "INITIAL_STOCK", None),  # system-only reason
        (1, "MADE_UP", None),
    ]
    for change, reason, note in cases:
        response = adjust(client, owner, ws, product["id"], change, reason, note)
        assert response.status_code == 422, (change, reason, response.text)
    non_integer = client.post(
        f"/api/v1/workspaces/{ws}/products/{product['id']}/adjustments",
        json={"quantity_change": 1.5, "reason": "RECEIVED"},
        headers=owner["headers"],
    )
    assert non_integer.status_code == 422
    assert api.stock(owner, ws, product["id"]) == 10


def test_ledger_always_reconciles_with_current_stock(api, client, owner):
    """Current stock == sum of all movements, and each row's resulting_stock is the running total."""
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=20)
    for change, reason in [(5, "RECEIVED"), (-7, "DAMAGED"), (-1, "CORRECTION"), (2, "RETURNED")]:
        assert adjust(client, owner, ws, product["id"], change, reason).status_code == 201
    history = client.get(
        f"/api/v1/workspaces/{ws}/products/{product['id']}/adjustments", params={"page_size": 100}, headers=owner["headers"]
    ).json()["items"]
    chronological = list(reversed(history))
    running = 0
    for row in chronological:
        running += row["quantity_change"]
        assert row["resulting_stock"] == running
    assert running == api.stock(owner, ws, product["id"]) == 19


def test_history_filters_by_product_reason_and_date(api, client, owner):
    ws = owner["workspace_id"]
    a = api.product(owner, ws, stock=10)
    b = api.product(owner, ws, stock=10)
    adjust(client, owner, ws, a["id"], 5, "RECEIVED")
    adjust(client, owner, ws, b["id"], -2, "DAMAGED")
    url = f"/api/v1/workspaces/{ws}/inventory/adjustments"

    def total(**params):
        response = client.get(url, params=params, headers=owner["headers"])
        assert response.status_code == 200, response.text
        return response.json()["total"]

    assert total() == 4  # two opening balances + two adjustments
    assert total(product_id=a["id"]) == 2
    assert total(reason="DAMAGED") == 1
    today, tomorrow, yesterday = date.today(), date.today() + timedelta(days=1), date.today() - timedelta(days=1)
    assert total(date_from=str(tomorrow)) == 0
    assert total(date_to=str(yesterday - timedelta(days=1))) == 0
    assert total(date_from=str(yesterday), date_to=str(tomorrow)) == 4
    assert client.get(url, params={"date_from": str(tomorrow), "date_to": str(today)}, headers=owner["headers"]).status_code == 422
    assert client.get(url, params={"product_id": "nope"}, headers=owner["headers"]).status_code == 422


def test_staff_can_adjust_and_view_history(api, client, owner, staff):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=3)
    response = adjust(client, staff, ws, product["id"], 2, "RECEIVED")
    assert response.status_code == 201
    assert response.json()["adjustment"]["user"]["id"] == staff["user"]["id"]
    assert client.get(f"/api/v1/workspaces/{ws}/inventory/adjustments", headers=staff["headers"]).status_code == 200


def test_adjusting_an_unknown_product_is_404(api, client, owner):
    from tests.conftest import new_uuid

    assert adjust(client, owner, owner["workspace_id"], new_uuid(), 1, "RECEIVED").status_code == 404
