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
    # Phase 15 additions are present with their defaults.
    assert settings["business_phone"] == ""
    assert settings["business_address"] == ""
    assert settings["default_rate_unit"] == "tola"
    assert settings["low_stock_threshold"] == "0"
    assert settings["receipt_note"] == ""


def test_new_profile_settings_round_trip(client):
    response = update_settings(
        client,
        {
            "business_phone": "+92 300 1234567",
            "business_address": "Gold Market, Lahore",
            "default_rate_unit": "gram",
            "low_stock_threshold": "12.5",
            "receipt_note": "Thank you for your business",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["business_phone"] == "+92 300 1234567"
    assert body["business_address"] == "Gold Market, Lahore"
    assert body["default_rate_unit"] == "gram"
    assert body["low_stock_threshold"] == "12.5"
    assert body["receipt_note"] == "Thank you for your business"


def test_optional_profile_fields_may_be_cleared(client):
    response = update_settings(
        client,
        {
            "business_phone": "",
            "business_address": "",
            "receipt_note": "",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["business_phone"] == ""


def test_invalid_rate_unit_is_rejected(client):
    response = update_settings(client, {"default_rate_unit": "ounce"})
    assert response.status_code == 422
    assert "default_rate_unit" in response.json()["detail"]


def test_invalid_low_stock_threshold_is_rejected(client):
    assert (
        update_settings(client, {"low_stock_threshold": "abc"}).status_code
        == 422
    )
    assert (
        update_settings(client, {"low_stock_threshold": "-5"}).status_code
        == 422
    )
    assert (
        update_settings(
            client, {"low_stock_threshold": "2000000"}
        ).status_code
        == 422
    )


def test_empty_required_fields_still_rejected(client):
    # Optional fields may be empty, required ones may not.
    assert update_settings(client, {"business_name": ""}).status_code == 422
    assert update_settings(client, {"default_location": ""}).status_code == 422
    assert update_settings(client, {"currency": ""}).status_code == 422


def test_system_info_requires_admin_and_hides_secrets(client, auth_headers):
    # Viewer/manager cannot read system info.
    assert (
        client.get(
            "/api/settings/system", headers=login_headers(client, "viewer")
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/settings/system", headers=login_headers(client, "manager")
        ).status_code
        == 403
    )

    response = client.get(
        "/api/settings/system", headers=login_headers(client, "admin")
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["app_version"]
    # Tests always run against SQLite; production uses PostgreSQL.
    assert body["database_backend"] == "sqlite" or body[
        "database_backend"
    ].startswith("postgres")
    assert isinstance(body["backup_encrypted"], bool)
    assert body["backup_retention_days"] >= 1
    assert body["backup_keep_min"] >= 1

    # No secrets may ever appear in this payload.
    raw = response.text
    assert "secret" not in raw.lower()
    assert "HISABPRO_BACKUP_KEY" not in raw
    assert "://" not in raw  # no database URL


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
