"""Concurrency: competing requests must not oversell stock or restore it twice.

These go through the real HTTP stack with one TestClient per thread, so each request gets its own
database connection and transaction - exactly like simultaneous users."""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app


def fire(calls):
    """Run callables simultaneously and return their results."""
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = [pool.submit(call) for call in calls]
        return [f.result() for f in futures]


def post_order(user, ws, items, key=None):
    headers = dict(user["headers"])
    if key:
        headers["Idempotency-Key"] = key

    def call():
        with TestClient(app) as thread_client:
            return thread_client.post(
                f"/api/v1/workspaces/{ws}/orders",
                json={"items": [{"product_id": pid, "quantity": qty} for pid, qty in items]},
                headers=headers,
            )

    return call


def test_competing_orders_cannot_consume_more_stock_than_exists(api, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=5)
    responses = fire([post_order(owner, ws, [(product["id"], 1)]) for _ in range(12)])

    statuses = sorted(r.status_code for r in responses)
    assert statuses.count(201) == 5 and statuses.count(409) == 7, statuses
    assert api.stock(owner, ws, product["id"]) == 0
    listing = api.client.get(f"/api/v1/workspaces/{ws}/orders", headers=owner["headers"]).json()
    assert listing["total"] == 5


def test_competing_large_orders_only_one_wins(api, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    responses = fire([post_order(owner, ws, [(product["id"], 7)]) for _ in range(6)])
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409, 409]
    assert api.stock(owner, ws, product["id"]) == 3


def test_multi_item_orders_in_opposite_order_do_not_deadlock_or_oversell(api, owner):
    ws = owner["workspace_id"]
    a = api.product(owner, ws, stock=6)
    b = api.product(owner, ws, stock=6)
    calls = []
    for i in range(10):  # half ask for (a, b), half for (b, a): classic lock-ordering deadlock setup
        items = [(a["id"], 1), (b["id"], 1)] if i % 2 == 0 else [(b["id"], 1), (a["id"], 1)]
        calls.append(post_order(owner, ws, items))
    responses = fire(calls)
    assert all(r.status_code in (201, 409) for r in responses), [r.text for r in responses]
    created = sum(1 for r in responses if r.status_code == 201)
    assert created == 6
    assert api.stock(owner, ws, a["id"]) == 0 and api.stock(owner, ws, b["id"]) == 0


def test_concurrent_cancellations_restore_stock_exactly_once(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    order = api.order(owner, ws, [(product["id"], 4)])

    def cancel():
        with TestClient(app) as thread_client:
            return thread_client.post(f"/api/v1/workspaces/{ws}/orders/{order['id']}/cancel", headers=owner["headers"])

    responses = fire([cancel for _ in range(8)])
    assert sorted(r.status_code for r in responses) == [200] + [409] * 7
    assert api.stock(owner, ws, product["id"]) == 10  # restored once, not 8 times
    history = client.get(
        f"/api/v1/workspaces/{ws}/products/{product['id']}/adjustments", params={"page_size": 100}, headers=owner["headers"]
    ).json()["items"]
    assert [h["reason"] for h in history].count("ORDER_CANCELLED") == 1


def test_cancel_racing_with_confirm_leaves_a_consistent_order(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    order = api.order(owner, ws, [(product["id"], 4)])

    def act(action):
        def call():
            with TestClient(app) as thread_client:
                return thread_client.post(f"/api/v1/workspaces/{ws}/orders/{order['id']}/{action}", headers=owner["headers"])
        return call

    responses = fire([act("cancel"), act("confirm"), act("cancel"), act("confirm")])
    final = client.get(f"/api/v1/workspaces/{ws}/orders/{order['id']}", headers=owner["headers"]).json()
    assert final["status"] == "CANCELLED"  # cancel is allowed from both PENDING and CONFIRMED
    assert api.stock(owner, ws, product["id"]) == 10
    assert all(r.status_code in (200, 409) for r in responses)


def test_concurrent_adjustments_never_go_negative_and_ledger_matches(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=5)

    def remove_two():
        with TestClient(app) as thread_client:
            return thread_client.post(
                f"/api/v1/workspaces/{ws}/products/{product['id']}/adjustments",
                json={"quantity_change": -2, "reason": "DAMAGED"},
                headers=owner["headers"],
            )

    responses = fire([remove_two for _ in range(6)])
    assert sorted(r.status_code for r in responses) == [201, 201, 409, 409, 409, 409]
    assert api.stock(owner, ws, product["id"]) == 1
    history = client.get(
        f"/api/v1/workspaces/{ws}/products/{product['id']}/adjustments", params={"page_size": 100}, headers=owner["headers"]
    ).json()["items"]
    assert sum(h["quantity_change"] for h in history) == 1


def test_concurrent_requests_with_the_same_idempotency_key_create_one_order(api, client, owner):
    ws = owner["workspace_id"]
    product = api.product(owner, ws, stock=10)
    responses = fire([post_order(owner, ws, [(product["id"], 2)], key="same-key-12345") for _ in range(6)])
    assert all(r.status_code in (200, 201) for r in responses), [r.text for r in responses]
    assert len({r.json()["id"] for r in responses}) == 1
    assert api.stock(owner, ws, product["id"]) == 8
    assert client.get(f"/api/v1/workspaces/{ws}/orders", headers=owner["headers"]).json()["total"] == 1
