from helpers import login_headers
from test_api import create_product, transaction_payload


def get_settings(client):
    response = client.get(
        "/api/settings", headers=login_headers(client, "viewer")
    )
    assert response.status_code == 200, response.text
    return response.json()


def update_settings(client, values, role="admin"):
    return client.put(
        "/api/settings",
        headers=login_headers(client, role),
        json=values,
    )


def test_settings_require_login(client):
    assert client.get("/api/settings").status_code == 401
    assert client.put("/api/settings", json={}).status_code == 401


def test_default_settings_are_returned(client):
    settings = get_settings(client)
    assert settings["currency"] == "PKR"
    assert settings["allow_negative_stock"] == "false"
    assert settings["default_location"] == "Main Store"


def test_admin_can_update_settings(client):
    response = update_settings(
        client, {"business_name": "SNJ Gold Lab", "currency": "PKR"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["business_name"] == "SNJ Gold Lab"


def test_manager_cannot_update_settings(client, auth_headers):
    response = client.put(
        "/api/settings",
        headers=auth_headers("manager"),
        json={"business_name": "Nope"},
    )
    assert response.status_code == 403


def test_unknown_setting_is_rejected(client):
    response = update_settings(client, {"not_a_setting": "x"})
    assert response.status_code == 422
    assert "Unknown setting" in response.json()["detail"]


def test_invalid_boolean_is_rejected(client):
    response = update_settings(client, {"allow_negative_stock": "yes"})
    assert response.status_code == 422


def test_negative_stock_setting_is_enforced(client):
    product = create_product(client)

    # No stock yet: sale must fail while negative stock is disallowed.
    sale_payload = transaction_payload(product["id"], weight=2, rate=100)
    blocked = client.post(
        "/api/sales",
        headers=login_headers(client, "operator"),
        json=sale_payload,
    )
    assert blocked.status_code == 409

    enabled = update_settings(client, {"allow_negative_stock": "true"})
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["allow_negative_stock"] == "true"

    allowed = client.post(
        "/api/sales",
        headers=login_headers(client, "operator"),
        json=sale_payload,
    )
    assert allowed.status_code == 201, allowed.text

    # Restore the safe default for any later assertions.
    assert update_settings(
        client, {"allow_negative_stock": "false"}
    ).status_code == 200
