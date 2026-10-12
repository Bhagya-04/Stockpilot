"""Product catalogue rules: SKU uniqueness, validation, edit/deactivate, search + pagination."""

from decimal import Decimal


def products_url(workspace_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/products"


# ---- SKU uniqueness -------------------------------------------------------------------------
def test_duplicate_sku_in_same_workspace_is_rejected(api, client, owner):
    api.product(owner, owner["workspace_id"], sku="WIDGET-1")
    response = client.post(
        products_url(owner["workspace_id"]),
        json={"name": "Another", "sku": "WIDGET-1", "unit_price": "1.00"},
        headers=owner["headers"],
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_SKU"


def test_sku_uniqueness_ignores_case_and_whitespace(api, client, owner):
    api.product(owner, owner["workspace_id"], sku="widget-1")
    response = client.post(
        products_url(owner["workspace_id"]),
        json={"name": "Another", "sku": "  WIDGET-1 ", "unit_price": "1.00"},
        headers=owner["headers"],
    )
    assert response.status_code == 409


def test_same_sku_is_allowed_in_a_different_workspace(api, owner, other_owner):
    first = api.product(owner, owner["workspace_id"], sku="SHARED-SKU")
    second = api.product(other_owner, other_owner["workspace_id"], sku="SHARED-SKU")
    assert first["id"] != second["id"]
    assert first["sku"] == second["sku"] == "SHARED-SKU"


def test_renaming_sku_to_an_existing_one_is_rejected(api, client, owner):
    api.product(owner, owner["workspace_id"], sku="A-1")
    b = api.product(owner, owner["workspace_id"], sku="B-1")
    response = client.patch(
        f"{products_url(owner['workspace_id'])}/{b['id']}", json={"sku": "a-1"}, headers=owner["headers"]
    )
    assert response.status_code == 409
    # re-sending its own SKU is not a conflict
    ok = client.patch(f"{products_url(owner['workspace_id'])}/{b['id']}", json={"sku": "B-1"}, headers=owner["headers"])
    assert ok.status_code == 200


# ---- validation -----------------------------------------------------------------------------
def test_invalid_input_is_rejected_by_the_server(client, owner):
    url = products_url(owner["workspace_id"])
    good = {"name": "Widget", "sku": "W-1", "unit_price": "5.00"}
    cases = {
        "unit_price": ["-1", "1.999", "abc", None],
        "stock_quantity": [-1, 1.5, "x"],
        "low_stock_threshold": [-5],
        "sku": ["", "   ", "bad sku!"],
        "name": ["", "   "],
    }
    for field, bad_values in cases.items():
        for bad in bad_values:
            response = client.post(url, json={**good, field: bad}, headers=owner["headers"])
            assert response.status_code == 422, (field, bad, response.text)
            assert any(d["field"] == field for d in response.json()["error"]["details"]), (field, bad)


def test_money_is_stored_exactly(api, owner):
    product = api.product(owner, owner["workspace_id"], price="19.99")
    assert Decimal(product["unit_price"]) == Decimal("19.99")


def test_stock_cannot_be_edited_through_the_product_endpoint(api, client, owner):
    product = api.product(owner, owner["workspace_id"], stock=5)
    response = client.patch(
        f"{products_url(owner['workspace_id'])}/{product['id']}", json={"stock_quantity": 999}, headers=owner["headers"]
    )
    assert response.status_code == 422
    assert api.stock(owner, owner["workspace_id"], product["id"]) == 5


def test_opening_stock_is_recorded_in_the_history(api, client, owner):
    product = api.product(owner, owner["workspace_id"], stock=12)
    history = client.get(
        f"{products_url(owner['workspace_id'])}/{product['id']}/adjustments", headers=owner["headers"]
    ).json()
    assert history["total"] == 1
    entry = history["items"][0]
    assert (entry["reason"], entry["quantity_change"], entry["resulting_stock"]) == ("INITIAL_STOCK", 12, 12)


# ---- edit / deactivate ----------------------------------------------------------------------
def test_edit_and_deactivate_product(api, client, owner):
    product = api.product(owner, owner["workspace_id"], name="Old", price="1.00")
    url = f"{products_url(owner['workspace_id'])}/{product['id']}"
    edited = client.patch(url, json={"name": "New", "unit_price": "2.50", "description": "d"}, headers=owner["headers"])
    assert edited.status_code == 200
    assert (edited.json()["name"], edited.json()["unit_price"], edited.json()["description"]) == ("New", "2.50", "d")
    assert edited.json()["updated_at"] >= product["updated_at"]

    deactivated = client.patch(url, json={"is_active": False}, headers=owner["headers"])
    assert deactivated.json()["is_active"] is False
    assert deactivated.json()["name"] == "New"  # untouched fields survive a partial update


# ---- search / filters / pagination ----------------------------------------------------------
def _seed_catalogue(api, owner):
    ws = owner["workspace_id"]
    api.product(owner, ws, sku="HAM-1", name="Claw Hammer", price="12.00", stock=50, threshold=10)
    api.product(owner, ws, sku="SAW-1", name="Hand Saw", price="20.00", stock=3, threshold=5)  # low stock
    api.product(owner, ws, sku="NAIL-1", name="Nails (100%)", price="4.00", stock=5, threshold=5)  # low (== threshold)
    api.product(owner, ws, sku="OLD-1", name="Retired Drill", price="99.00", stock=0, threshold=1, is_active=False)


def test_search_filters_and_low_stock(api, client, owner):
    _seed_catalogue(api, owner)
    url = products_url(owner["workspace_id"])

    def skus(**params):
        response = client.get(url, params=params, headers=owner["headers"])
        assert response.status_code == 200, response.text
        return [p["sku"] for p in response.json()["items"]]

    assert skus() == ["HAM-1", "SAW-1", "NAIL-1", "OLD-1"]  # default sort: name asc (Claw, Hand, Nails, Retired)
    assert skus(q="hammer") == ["HAM-1"]
    assert skus(q="saw") == ["SAW-1"]
    assert skus(q="%") == ["NAIL-1"]  # LIKE wildcards are escaped, matched literally
    assert skus(sku="nail-1") == ["NAIL-1"]
    assert skus(active="inactive") == ["OLD-1"]
    assert sorted(skus(active="active")) == ["HAM-1", "NAIL-1", "SAW-1"]
    # low stock = active AND stock <= threshold  (inactive OLD-1 is excluded even though 0 <= 1)
    assert sorted(skus(low_stock="true")) == ["NAIL-1", "SAW-1"]
    assert sorted(skus(low_stock="false")) == ["HAM-1", "OLD-1"]
    assert skus(sort_by="unit_price", sort_dir="desc") == ["OLD-1", "SAW-1", "HAM-1", "NAIL-1"]


def test_pagination_and_parameter_validation(api, client, owner):
    for i in range(7):
        api.product(owner, owner["workspace_id"], sku=f"P-{i}", name=f"Item {i}")
    url = products_url(owner["workspace_id"])
    page2 = client.get(url, params={"page": 2, "page_size": 3}, headers=owner["headers"]).json()
    assert (page2["total"], page2["page"], page2["page_size"], page2["pages"]) == (7, 2, 3, 3)
    assert [p["sku"] for p in page2["items"]] == ["P-3", "P-4", "P-5"]
    beyond = client.get(url, params={"page": 99, "page_size": 3}, headers=owner["headers"]).json()
    assert beyond["items"] == [] and beyond["total"] == 7

    for params in ({"page": 0}, {"page_size": 0}, {"page_size": 101}, {"sort_by": "password"}, {"active": "maybe"}):
        assert client.get(url, params=params, headers=owner["headers"]).status_code == 422, params


def test_empty_workspace_lists_cleanly(client, owner):
    body = client.get(products_url(owner["workspace_id"]), headers=owner["headers"]).json()
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0}


# ---- role enforcement -----------------------------------------------------------------------
def test_staff_can_view_but_not_create_edit_or_deactivate_products(api, client, owner, staff):
    ws = owner["workspace_id"]
    product = api.product(owner, ws)
    assert client.get(products_url(ws), headers=staff["headers"]).status_code == 200
    assert client.get(f"{products_url(ws)}/{product['id']}", headers=staff["headers"]).status_code == 200

    create = client.post(products_url(ws), json={"name": "x", "sku": "X-1", "unit_price": "1"}, headers=staff["headers"])
    edit = client.patch(f"{products_url(ws)}/{product['id']}", json={"name": "hacked"}, headers=staff["headers"])
    deactivate = client.patch(f"{products_url(ws)}/{product['id']}", json={"is_active": False}, headers=staff["headers"])
    assert create.status_code == edit.status_code == deactivate.status_code == 403
    assert create.json()["error"]["code"] == "PERMISSION_DENIED"
    assert api.get_product(owner, ws, product["id"])["is_active"] is True
