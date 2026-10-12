from tests.conftest import PASSWORD


def test_register_returns_token_and_creates_owner_workspace(api, client):
    user = api.register("ann@example.com", workspace_name="Ann's Shop", name="Ann")
    me = client.get("/api/v1/auth/me", headers=user["headers"])
    assert me.status_code == 200
    assert me.json()["email"] == "ann@example.com"
    assert "password" not in me.text and "hash" not in me.text
    workspaces = api.workspaces(user["headers"])
    assert [(w["name"], w["role"]) for w in workspaces] == [("Ann's Shop", "OWNER")]


def test_email_is_case_insensitive_and_unique(api, client):
    api.register("Dup@Example.com")
    response = client.post(
        "/api/v1/auth/register", json={"email": "dup@example.com", "password": PASSWORD, "full_name": "X"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_TAKEN"


def test_login_success_and_failure_are_indistinguishable(api, client):
    api.register("login@example.com")
    ok = client.post("/api/v1/auth/login", json={"email": "LOGIN@example.com", "password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["access_token"]

    wrong_password = client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "nope-nope-1"})
    unknown_user = client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-1"})
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json()["error"]["message"] == unknown_user.json()["error"]["message"]


def test_weak_password_is_rejected_with_field_error(client):
    response = client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "short", "full_name": "A"})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert any(d["field"] == "password" for d in body["details"])
    assert '"input"' not in response.text  # the submitted value is never echoed back


def test_private_routes_require_a_valid_token(client, owner):
    url = f"/api/v1/workspaces/{owner['workspace_id']}/products"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"Authorization": "Bearer garbage"}).status_code == 401
    assert client.get("/api/v1/workspaces").status_code == 401
    assert client.get(url, headers=owner["headers"]).status_code == 200


def test_identity_comes_from_the_token_not_the_request_body(api, client, owner):
    """A client-supplied user id is ignored: the audit row is attributed to the authenticated user."""
    product = api.product(owner, owner["workspace_id"], stock=1)
    response = client.post(
        f"/api/v1/workspaces/{owner['workspace_id']}/products/{product['id']}/adjustments",
        json={"quantity_change": 1, "reason": "RECEIVED", "user_id": "00000000-0000-0000-0000-000000000000"},
        headers=owner["headers"],
    )
    assert response.status_code == 201
    assert response.json()["adjustment"]["user"]["id"] == owner["user"]["id"]


def test_errors_use_the_standard_envelope_and_hide_internals(client, owner):
    response = client.get(f"/api/v1/workspaces/{owner['workspace_id']}/products/not-a-uuid", headers=owner["headers"])
    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details", "request_id"}
    assert response.headers["x-request-id"] == body["error"]["request_id"]
    assert "Traceback" not in response.text


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}
