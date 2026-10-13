from helpers import login_headers
from test_api import create_product


def latest_logs(client, **params):
    response = client.get(
        "/api/audit",
        params=params,
        headers=login_headers(client, "admin"),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_audit_requires_admin(client, auth_headers):
    assert client.get("/api/audit").status_code == 401

    for role in ("viewer", "operator", "manager"):
        response = client.get("/api/audit", headers=auth_headers(role))
        assert response.status_code == 403, role

    assert client.get(
        "/api/audit", headers=auth_headers("admin")
    ).status_code == 200


def test_product_creation_is_audited(client):
    product = create_product(client)
    assert product["sku"] == "GOLD-001"

    logs = latest_logs(client, action="product.create", entity_type="product")
    assert any("GOLD-001" in entry["detail"] for entry in logs)


def test_payment_is_audited(client):
    product = create_product(client)
    purchase = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json={
            "product_id": product["id"],
            "quantity_grams": 5,
            "gross_weight_grams": 5,
            "net_weight_grams": 5,
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": 100,
            "charges": 0,
            "amount_paid": 0,
            "payment_method": "cash",
            "party_name": "Audit Party",
            "location": "Main Store",
            "created_by": "Pytest",
        },
    )
    assert purchase.status_code == 201, purchase.text

    response = client.post(
        f"/api/transactions/{purchase.json()['id']}/payments",
        headers=login_headers(client, "operator"),
        json={
            "amount": 100,
            "method": "bank_transfer",
            "note": "Audit test",
            "recorded_by": "Pytest",
        },
    )
    assert response.status_code == 201, response.text

    logs = latest_logs(client, action="payment.create")
    assert any("100" in entry["detail"] for entry in logs)


def test_cancellation_is_audited(client):
    product = create_product(client)
    purchase = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json={
            "product_id": product["id"],
            "quantity_grams": 5,
            "gross_weight_grams": 5,
            "net_weight_grams": 5,
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": 100,
            "charges": 0,
            "amount_paid": 0,
            "payment_method": "cash",
            "party_name": "Audit Party",
            "location": "Main Store",
            "created_by": "Pytest",
        },
    )
    assert purchase.status_code == 201, purchase.text

    cancel = client.post(
        f"/api/transactions/{purchase.json()['id']}/cancel",
        headers=login_headers(client, "manager"),
        json={"reason": "Audit trail test"},
    )
    assert cancel.status_code == 200, cancel.text

    logs = latest_logs(client, action="transaction.cancel")
    assert any("Audit trail test" in entry["detail"] for entry in logs)
    assert all(entry["username"].startswith("test_") for entry in logs)


def test_audit_filters_by_username(client):
    create_product(client)

    matching = latest_logs(client, username="test_manager")
    assert matching
    assert all(entry["username"] == "test_manager" for entry in matching)
