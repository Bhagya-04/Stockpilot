"""Workspace isolation and role enforcement. The 'attacker' is a legitimate member of workspace B
who tries to reach workspace A's data by swapping ids in URLs or request bodies."""

from tests.conftest import new_uuid


def test_non_member_gets_404_on_every_workspace_route(api, client, owner, other_owner):
    """404 (not 403) so the response is identical for 'does not exist' and 'not yours'."""
    ws = owner["workspace_id"]  # victim workspace
    product = api.product(owner, ws, stock=5)
    order = api.order(owner, ws, [(product["id"], 1)])
    attacker = other_owner["headers"]
    base = f"/api/v1/workspaces/{ws}"

    requests = [
        ("get", f"{base}/products", None),
        ("post", f"{base}/products", {"name": "x", "sku": "X", "unit_price": "1"}),
        ("get", f"{base}/products/{product['id']}", None),
        ("patch", f"{base}/products/{product['id']}", {"name": "pwned"}),
        ("post", f"{base}/products/{product['id']}/adjustments", {"quantity_change": 5, "reason": "RECEIVED"}),
        ("get", f"{base}/products/{product['id']}/adjustments", None),
        ("get", f"{base}/inventory/adjustments", None),
        ("get", f"{base}/orders", None),
        ("post", f"{base}/orders", {"items": [{"product_id": product["id"], "quantity": 1}]}),
        ("get", f"{base}/orders/{order['id']}", None),
        ("post", f"{base}/orders/{order['id']}/cancel", None),
        ("post", f"{base}/orders/{order['id']}/confirm", None),
        ("get", f"{base}/dashboard", None),
        ("get", f"{base}/members", None),
        ("post", f"{base}/members", {"email": "other@example.com", "role": "OWNER"}),
    ]
    unknown_ws = new_uuid()
    for method, url, body in requests:
        response = getattr(client, method)(url, headers=attacker, **({"json": body} if body else {}))
        assert response.status_code == 404, (method, url, response.status_code, response.text)
        assert response.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"
        # byte-for-byte the same answer as for a workspace that does not exist at all
        ghost = getattr(client, method)(url.replace(ws, unknown_ws), headers=attacker, **({"json": body} if body else {}))
        assert ghost.status_code == 404 and ghost.json()["error"]["message"] == response.json()["error"]["message"]

    # nothing was changed or leaked
    assert api.stock(owner, ws, product["id"]) == 4  # 5 - 1 from the legitimate order only
    assert client.get(f"{base}/orders/{order['id']}", headers=owner["headers"]).json()["status"] == "PENDING"
    assert api.get_product(owner, ws, product["id"])["name"] == product["name"]


def test_member_cannot_reach_foreign_ids_through_their_own_workspace(api, client, owner, other_owner):
    """Swapping only the product/order id while keeping a workspace you belong to must also fail."""
    ws_a, ws_b = owner["workspace_id"], other_owner["workspace_id"]
    product_a = api.product(owner, ws_a, stock=5)
    order_a = api.order(owner, ws_a, [(product_a["id"], 1)])
    attacker = other_owner["headers"]
    base_b = f"/api/v1/workspaces/{ws_b}"

    assert client.get(f"{base_b}/products/{product_a['id']}", headers=attacker).status_code == 404
    assert client.patch(f"{base_b}/products/{product_a['id']}", json={"name": "pwned"}, headers=attacker).status_code == 404
    adjust = client.post(
        f"{base_b}/products/{product_a['id']}/adjustments", json={"quantity_change": 50, "reason": "RECEIVED"}, headers=attacker
    )
    assert adjust.status_code == 404
    assert client.get(f"{base_b}/products/{product_a['id']}/adjustments", headers=attacker).status_code == 404
    assert client.get(f"{base_b}/inventory/adjustments", params={"product_id": product_a["id"]}, headers=attacker).status_code == 404
    assert client.get(f"{base_b}/orders/{order_a['id']}", headers=attacker).status_code == 404
    assert client.post(f"{base_b}/orders/{order_a['id']}/cancel", headers=attacker).status_code == 404
    # listing in my own workspace never includes the other workspace's rows
    assert client.get(f"{base_b}/products", headers=attacker).json()["total"] == 0
    assert client.get(f"{base_b}/orders", headers=attacker).json()["total"] == 0
    assert client.get(f"{base_b}/orders", params={"q": order_a["id"]}, headers=attacker).json()["total"] == 0
    assert client.get(f"{base_b}/inventory/adjustments", headers=attacker).json()["total"] == 0

    assert api.stock(owner, ws_a, product_a["id"]) == 4
    assert api.get_product(owner, ws_a, product_a["id"])["name"] == product_a["name"]


def test_order_cannot_include_another_workspaces_product(api, client, owner, other_owner):
    ws_a, ws_b = owner["workspace_id"], other_owner["workspace_id"]
    foreign = api.product(owner, ws_a, stock=5)
    mine = api.product(other_owner, ws_b, stock=5)
    response = client.post(
        f"/api/v1/workspaces/{ws_b}/orders",
        json={"items": [{"product_id": mine["id"], "quantity": 1}, {"product_id": foreign["id"], "quantity": 1}]},
        headers=other_owner["headers"],
    )
    assert response.status_code == 422
    detail = response.json()["error"]["details"][0]
    assert detail["code"] == "PRODUCT_NOT_FOUND"  # same answer as for an id that doesn't exist at all
    assert api.stock(owner, ws_a, foreign["id"]) == 5
    assert api.stock(other_owner, ws_b, mine["id"]) == 5  # all-or-nothing
    assert client.get(f"/api/v1/workspaces/{ws_b}/orders", headers=other_owner["headers"]).json()["total"] == 0


def test_workspace_list_only_contains_own_workspaces(api, owner, other_owner):
    assert [w["id"] for w in api.workspaces(owner["headers"])] == [owner["workspace_id"]]
    assert [w["id"] for w in api.workspaces(other_owner["headers"])] == [other_owner["workspace_id"]]


def test_user_can_belong_to_several_workspaces_with_different_roles(api, client, owner, other_owner):
    api.add_staff(other_owner, other_owner["workspace_id"], "owner@example.com")
    workspaces = {w["id"]: w["role"] for w in api.workspaces(owner["headers"])}
    assert workspaces == {owner["workspace_id"]: "OWNER", other_owner["workspace_id"]: "STAFF"}
    # in the workspace where they are only STAFF, owner-only actions are forbidden (not 404: they are a member)
    denied = client.get(f"/api/v1/workspaces/{other_owner['workspace_id']}/dashboard", headers=owner["headers"])
    assert denied.status_code == 403
    # and in their own workspace everything works
    assert client.get(f"/api/v1/workspaces/{owner['workspace_id']}/dashboard", headers=owner["headers"]).status_code == 200


def test_staff_is_forbidden_from_owner_only_actions(api, client, owner, staff):
    ws = owner["workspace_id"]
    base = f"/api/v1/workspaces/{ws}"
    attempts = [
        ("get", f"{base}/dashboard", None),
        ("get", f"{base}/members", None),
        ("post", f"{base}/members", {"email": "owner@example.com", "role": "STAFF"}),
        ("patch", f"{base}/members/{staff['user']['id']}", {"role": "OWNER"}),  # self-promotion
        ("delete", f"{base}/members/{owner['user']['id']}", None),
    ]
    for method, url, body in attempts:
        response = getattr(client, method)(url, headers=staff["headers"], **({"json": body} if body else {}))
        assert response.status_code == 403, (method, url, response.text)
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    still_staff = {w["id"]: w["role"] for w in api.workspaces(staff["headers"])}
    assert still_staff[ws] == "STAFF"


def test_owner_manages_membership(api, client, owner, staff):
    ws = owner["workspace_id"]
    base = f"/api/v1/workspaces/{ws}/members"
    members = client.get(base, headers=owner["headers"]).json()
    assert {(m["email"], m["role"]) for m in members} == {("owner@example.com", "OWNER"), ("staff@example.com", "STAFF")}

    duplicate = client.post(base, json={"email": "staff@example.com"}, headers=owner["headers"])
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "ALREADY_MEMBER"
    unknown = client.post(base, json={"email": "nobody@example.com"}, headers=owner["headers"])
    assert unknown.status_code == 404

    # staff access is revoked immediately on removal (role/membership is read on every request)
    assert client.get(f"/api/v1/workspaces/{ws}/products", headers=staff["headers"]).status_code == 200
    assert client.delete(f"{base}/{staff['user']['id']}", headers=owner["headers"]).status_code == 204
    assert client.get(f"/api/v1/workspaces/{ws}/products", headers=staff["headers"]).status_code == 404


def test_last_owner_cannot_be_removed_or_demoted(api, client, owner):
    ws = owner["workspace_id"]
    me = owner["user"]["id"]
    base = f"/api/v1/workspaces/{ws}/members/{me}"
    assert client.delete(base, headers=owner["headers"]).status_code == 409
    demote = client.patch(base, json={"role": "STAFF"}, headers=owner["headers"])
    assert demote.status_code == 409 and demote.json()["error"]["code"] == "LAST_OWNER"

    api.register("second@example.com")
    api.add_staff(owner, ws, "second@example.com")
    promoted = client.patch(
        f"/api/v1/workspaces/{ws}/members/{api.client.post('/api/v1/auth/login', json={'email': 'second@example.com', 'password': 'Sup3r-secret-pw'}).json()['user']['id']}",
        json={"role": "OWNER"},
        headers=owner["headers"],
    )
    assert promoted.status_code == 200
    assert client.delete(base, headers=owner["headers"]).status_code == 204  # now allowed: another owner remains


def test_user_can_create_additional_workspaces(api, client, owner):
    response = client.post("/api/v1/workspaces", json={"name": "Second Shop"}, headers=owner["headers"])
    assert response.status_code == 201 and response.json()["role"] == "OWNER"
    assert len(api.workspaces(owner["headers"])) == 2
