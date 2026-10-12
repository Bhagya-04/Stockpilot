"""Order rules: server-side totals, snapshots, atomicity, lifecycle, cancellation, idempotency."""

from decimal import Decimal

from tests.conftest import new_uuid


def orders_url(ws: str) -> str:
    return f"/api/v1/workspaces/{ws}/orders"


def history(client, user, ws, product_id):
    body = client.get(
        f"/api/v1/workspaces/{ws}/products/{product_id}/adjustments", params={"page_size": 100}, headers=user["headers"]
    ).json()
    return list(reversed(body["items"]))  # oldest first


# ---- totals & snapshots ---------------------------------------------------------------------
def test_server_calculates_line_and_order_totals(api, owner):
    ws = owner["workspace_id"]
    a = api.product(owner, ws, price="19.99", stock=10)
    b = api.product(owner, ws, price="0.10", stock=10)
    order = api.order(owner, ws, [(a["id"], 3), (b["id"], 3)])
    lines = {line["product_id"]: line for line in order["items"]}
    assert Decimal(lines[a["id"]]["line_total"]) == Decimal("59.97")
    assert Decimal(lines[b["id"]]["line_total"]) == Decimal("0.30")
    assert Decimal(order["total_amount"]) == Decimal("60.27")
    assert order["status"] == "PENDING"
    assert order["creator"]["id"] == owner["user"]["id"]
    assert order["display_number"].startswith("ORD-")


def test_client_supplied_totals_and_prices_are_ignored(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, price="10.00", stock=5)
    response = client.post(
        orders_url(ws),
        json={
            "items": [{"product_id": product["id"], "quantity": 2, "unit_price": "0.01", "line_total": "0.02"}],
            "total_amount": "0.02",
            "total": "0.02",
            "status": "COMPLETED",
            "created_by": new_uuid(),
        },
        headers=owner["headers"],
    )
    assert response.status_code == 201
    order = response.json()
    assert Decimal(order["total_amount"]) == Decimal("20.00")
    assert Decimal(order["items"][0]["unit_price"]) == Decimal("10.00")
    assert order["status"] == "PENDING"
    assert order["creator"]["id"] == owner["user"]["id"]


def test_price_change_does_not_alter_existing_orders(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, price="10.00", name="Gadget", sku="GAD-1", stock=10)
    order = api.order(owner, ws, [(product["id"], 2)])

    client.patch(
        f"/api/v1/workspaces/{ws}/products/{product['id']}",
        json={"unit_price": "99.00", "name": "Renamed", "sku": "NEW-SKU"},
        headers=owner["headers"],
    )
    reread = client.get(f"{orders_url(ws)}/{order['id']}", headers=owner["headers"]).json()
    line = reread["items"][0]
    assert (line["product_name"], line["sku"], Decimal(line["unit_price"]), Decimal(line["line_total"])) == (
        "Gadget", "GAD-1", Decimal("10.00"), Decimal("20.00"),
    )
    assert Decimal(reread["total_amount"]) == Decimal("20.00")

    new_order = api.order(owner, ws, [(product["id"], 1)])  # new orders use the new price
    assert Decimal(new_order["total_amount"]) == Decimal("99.00")


# ---- stock strategy: reserve at creation ----------------------------------------------------
def test_creating_an_order_reserves_stock_and_writes_audit_rows(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    order = api.order(owner, ws, [(product["id"], 4)])
    assert api.stock(owner, ws, product["id"]) == 6
    reserved = history(client, owner, ws, product["id"])[-1]
    assert (reserved["reason"], reserved["quantity_change"], reserved["resulting_stock"], reserved["order_id"]) == (
        "ORDER_RESERVED", -4, 6, order["id"],
    )


def test_insufficient_stock_rejects_the_order(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=3)
    response = client.post(
        orders_url(ws), json={"items": [{"product_id": product["id"], "quantity": 4}]}, headers=owner["headers"]
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INSUFFICIENT_STOCK"
    assert error["details"][0]["available"] == 3 and error["details"][0]["requested"] == 4
    assert api.stock(owner, ws, product["id"]) == 3
    assert client.get(orders_url(ws), headers=owner["headers"]).json()["total"] == 0


def test_inactive_product_cannot_be_ordered_but_history_is_kept(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    order = api.order(owner, ws, [(product["id"], 1)])
    client.patch(f"/api/v1/workspaces/{ws}/products/{product['id']}", json={"is_active": False}, headers=owner["headers"])

    response = client.post(
        orders_url(ws), json={"items": [{"product_id": product["id"], "quantity": 1}]}, headers=owner["headers"]
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["code"] == "PRODUCT_INACTIVE"
    assert client.get(f"{orders_url(ws)}/{order['id']}", headers=owner["headers"]).json()["items"][0]["quantity"] == 1


def test_order_validation(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    pid = product["id"]
    for payload in (
        {"items": []},
        {"items": [{"product_id": pid, "quantity": 0}]},
        {"items": [{"product_id": pid, "quantity": -1}]},
        {"items": [{"product_id": pid, "quantity": 1.5}]},
        {"items": [{"product_id": "not-a-uuid", "quantity": 1}]},
        {"items": [{"product_id": new_uuid(), "quantity": 1}]},  # unknown product
        {},
    ):
        response = client.post(orders_url(ws), json=payload, headers=owner["headers"])
        assert response.status_code in (422,), (payload, response.text)
    assert api.stock(owner, ws, pid) == 10


def test_duplicate_lines_for_the_same_product_are_merged(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, price="2.00", stock=10)
    order = api.order(owner, ws, [(product["id"], 2), (product["id"], 3)])
    assert len(order["items"]) == 1 and order["items"][0]["quantity"] == 5
    assert Decimal(order["total_amount"]) == Decimal("10.00")
    assert api.stock(owner, ws, product["id"]) == 5
    # merged quantity is what is checked against stock
    too_many = client.post(
        orders_url(ws),
        json={"items": [{"product_id": product["id"], "quantity": 3}, {"product_id": product["id"], "quantity": 3}]},
        headers=owner["headers"],
    )
    assert too_many.status_code == 409


# ---- atomicity ------------------------------------------------------------------------------
def test_multi_item_order_is_all_or_nothing(api, client, owner):
    ws = owner["workspace_id"]
    ok_a = api.product(owner, ws, stock=10)
    short = api.product(owner, ws, stock=1)
    ok_b = api.product(owner, ws, stock=10)
    response = client.post(
        orders_url(ws),
        json={
            "items": [
                {"product_id": ok_a["id"], "quantity": 2},
                {"product_id": short["id"], "quantity": 5},  # the failing line is in the middle
                {"product_id": ok_b["id"], "quantity": 2},
            ]
        },
        headers=owner["headers"],
    )
    assert response.status_code == 409
    assert [api.stock(owner, ws, p["id"]) for p in (ok_a, short, ok_b)] == [10, 1, 10]
    assert client.get(orders_url(ws), headers=owner["headers"]).json()["total"] == 0
    for product in (ok_a, short, ok_b):  # no ORDER_RESERVED rows leaked either
        assert [h["reason"] for h in history(client, owner, ws, product["id"])] == ["INITIAL_STOCK"]


def test_mixed_failures_report_every_problem_and_write_nothing(api, client, owner):
    ws = owner["workspace_id"]
    inactive = api.product(owner, ws, stock=5, is_active=False)
    short = api.product(owner, ws, stock=1)
    response = client.post(
        orders_url(ws),
        json={
            "items": [
                {"product_id": inactive["id"], "quantity": 1},
                {"product_id": short["id"], "quantity": 9},
                {"product_id": new_uuid(), "quantity": 1},
            ]
        },
        headers=owner["headers"],
    )
    assert response.status_code == 422
    codes = sorted(d["code"] for d in response.json()["error"]["details"])
    assert codes == ["INSUFFICIENT_STOCK", "PRODUCT_INACTIVE", "PRODUCT_NOT_FOUND"]
    assert client.get(orders_url(ws), headers=owner["headers"]).json()["total"] == 0


# ---- lifecycle ------------------------------------------------------------------------------
def test_happy_path_pending_confirmed_completed_keeps_the_deduction(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    order = api.order(owner, ws, [(product["id"], 3)])
    assert api.stock(owner, ws, product["id"]) == 7

    confirmed = api.order_action(owner, ws, order["id"], "confirm")
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "CONFIRMED"
    assert confirmed.json()["confirmed_at"]
    assert api.stock(owner, ws, product["id"]) == 7  # confirmation does not deduct again

    completed = api.order_action(owner, ws, order["id"], "complete")
    assert completed.status_code == 200 and completed.json()["status"] == "COMPLETED"
    assert completed.json()["completed_at"]
    assert api.stock(owner, ws, product["id"]) == 7  # deduction retained
    assert [h["reason"] for h in history(client, owner, ws, product["id"])] == ["INITIAL_STOCK", "ORDER_RESERVED"]


def test_invalid_transitions_are_rejected_and_change_nothing(api, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    order = api.order(owner, ws, [(product["id"], 2)])

    skip = api.order_action(owner, ws, order["id"], "complete")  # PENDING -> COMPLETED not allowed
    assert skip.status_code == 409
    assert skip.json()["error"]["code"] == "INVALID_TRANSITION"

    api.order_action(owner, ws, order["id"], "confirm")
    assert api.order_action(owner, ws, order["id"], "confirm").status_code == 409  # CONFIRMED -> CONFIRMED
    api.order_action(owner, ws, order["id"], "complete")
    for action in ("confirm", "complete", "cancel"):  # COMPLETED is terminal
        assert api.order_action(owner, ws, order["id"], action).status_code == 409
    assert api.stock(owner, ws, product["id"]) == 8  # a completed order is never "un-sold"


def test_cancelling_a_pending_order_restores_stock(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    order = api.order(owner, ws, [(product["id"], 4)])
    cancelled = api.order_action(owner, ws, order["id"], "cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["cancelled_at"]
    assert api.stock(owner, ws, product["id"]) == 10
    last = history(client, owner, ws, product["id"])[-1]
    assert (last["reason"], last["quantity_change"], last["resulting_stock"]) == ("ORDER_CANCELLED", 4, 10)


def test_cancelling_a_confirmed_multi_item_order_restores_every_line(api, owner):
    ws = owner["workspace_id"]
    a = api.product(owner, ws, stock=10)
    b = api.product(owner, ws, stock=5)
    order = api.order(owner, ws, [(a["id"], 3), (b["id"], 5)])
    assert (api.stock(owner, ws, a["id"]), api.stock(owner, ws, b["id"])) == (7, 0)
    api.order_action(owner, ws, order["id"], "confirm")
    assert api.order_action(owner, ws, order["id"], "cancel").status_code == 200
    assert (api.stock(owner, ws, a["id"]), api.stock(owner, ws, b["id"])) == (10, 5)


def test_repeated_cancellation_restores_stock_only_once(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    order = api.order(owner, ws, [(product["id"], 4)])

    first = api.order_action(owner, ws, order["id"], "cancel")
    assert first.status_code == 200
    for _ in range(3):  # client retries
        retry = api.order_action(owner, ws, order["id"], "cancel")
        assert retry.status_code == 409
        assert retry.json()["error"]["code"] == "INVALID_TRANSITION"
    assert api.stock(owner, ws, product["id"]) == 10  # not 14, 18, ...
    reasons = [h["reason"] for h in history(client, owner, ws, product["id"])]
    assert reasons.count("ORDER_CANCELLED") == 1


def test_cancellation_restores_stock_even_if_product_was_deactivated(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=5)
    order = api.order(owner, ws, [(product["id"], 5)])
    client.patch(f"/api/v1/workspaces/{ws}/products/{product['id']}", json={"is_active": False}, headers=owner["headers"])
    assert api.order_action(owner, ws, order["id"], "cancel").status_code == 200
    assert api.stock(owner, ws, product["id"]) == 5


def test_staff_can_create_and_progress_orders(api, owner, staff):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    order = api.order(staff, ws, [(product["id"], 1)])
    assert order["creator"]["id"] == staff["user"]["id"]
    assert api.order_action(staff, ws, order["id"], "confirm").status_code == 200
    assert api.order_action(staff, ws, order["id"], "cancel").status_code == 200


# ---- idempotent creation --------------------------------------------------------------------
def test_retrying_with_the_same_idempotency_key_does_not_double_book(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    headers = {**owner["headers"], "Idempotency-Key": "retry-key-0001"}
    payload = {"items": [{"product_id": product["id"], "quantity": 3}]}
    first = client.post(orders_url(ws), json=payload, headers=headers)
    second = client.post(orders_url(ws), json=payload, headers=headers)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert api.stock(owner, ws, product["id"]) == 7
    assert client.get(orders_url(ws), headers=owner["headers"]).json()["total"] == 1


def test_invalid_idempotency_key_is_rejected(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=1)
    response = client.post(
        orders_url(ws),
        json={"items": [{"product_id": product["id"], "quantity": 1}]},
        headers={**owner["headers"], "Idempotency-Key": "short"},
    )
    assert response.status_code == 422


# ---- listing / filtering --------------------------------------------------------------------
def test_order_list_filters_sorting_and_pagination(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, price="5.00", stock=100)
    created = [api.order(owner, ws, [(product["id"], n)]) for n in (1, 2, 3, 4)]
    api.order_action(owner, ws, created[0]["id"], "confirm")
    api.order_action(owner, ws, created[1]["id"], "cancel")

    def listing(**params):
        response = client.get(orders_url(ws), params=params, headers=owner["headers"])
        assert response.status_code == 200, response.text
        return response.json()

    assert listing()["total"] == 4
    assert [o["id"] for o in listing()["items"]] == [o["id"] for o in reversed(created)]  # newest first
    assert listing(status="CONFIRMED")["total"] == 1
    assert listing(status="CANCELLED")["items"][0]["id"] == created[1]["id"]
    assert listing(q=created[2]["display_number"])["items"][0]["id"] == created[2]["id"]
    assert listing(q=created[3]["id"])["items"][0]["id"] == created[3]["id"]
    assert listing(q="ORD-999999")["total"] == 0
    assert listing(q="garbage")["total"] == 0
    assert [Decimal(o["total_amount"]) for o in listing(sort_by="total_amount", sort_dir="asc")["items"]] == [
        Decimal("5.00"), Decimal("10.00"), Decimal("15.00"), Decimal("20.00"),
    ]
    page = listing(page=2, page_size=3)
    assert (page["total"], len(page["items"]), page["pages"]) == (4, 1, 2)
    assert listing(date_from="2000-01-01", date_to="2000-01-02")["total"] == 0
    for bad in ({"status": "NOPE"}, {"page_size": 500}, {"date_from": "yesterday"}, {"sort_by": "x"}):
        assert client.get(orders_url(ws), params=bad, headers=owner["headers"]).status_code == 422, bad
