from helpers import login_headers
from decimal import Decimal


API_HEADERS = {"X-API-Key": "test-api-key"}


def create_product(client, sku="GOLD-001"):
    response = client.post(
        "/api/products",
        headers=login_headers(client),
        json={
            "sku": sku,
            "name": "Test Gold",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 100,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def transaction_payload(
    product_id,
    weight,
    rate=100,
    amount_paid=0,
    payment_method="cash",
):
    return {
        "product_id": product_id,
        "quantity_grams": weight,
        "gross_weight_grams": weight,
        "net_weight_grams": weight,
        "deduction_grams": 0,
        "purity": 100,
        "rate_per_gram": rate,
        "charges": 0,
        "amount_paid": amount_paid,
        "payment_method": payment_method,
        "party_name": "Test Customer",
        "location": "Main Store",
        "created_by": "Pytest",
    }


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_product_create_list_and_duplicate_sku(client):
    product = create_product(client)

    assert product["sku"] == "GOLD-001"
    assert product["metal"] == "gold"

    response = client.get("/api/products", headers=login_headers(client))
    assert response.status_code == 200
    assert any(item["id"] == product["id"] for item in response.json())

    duplicate = client.post(
        "/api/products",
        headers=login_headers(client),
        json={
            "sku": "GOLD-001",
            "name": "Duplicate Gold",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 100,
        },
    )
    assert duplicate.status_code == 409


def test_product_creation_requires_api_key(client):
    response = client.post(
        "/api/products",
        json={
            "sku": "NO-KEY",
            "name": "Unauthorized Product",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 100,
        },
    )

    assert response.status_code == 401


def test_rate_history_keeps_only_latest_rate_active(client):
    first = client.post(
        "/api/rates",
        headers=API_HEADERS,
        json={
            "metal": "gold",
            "purity": 100,
            "rate_per_gram": 10000,
            "source_note": "First test rate",
            "verified_by": "Pytest",
        },
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/rates",
        headers=API_HEADERS,
        json={
            "metal": "gold",
            "purity": 100,
            "rate_per_gram": 10500,
            "source_note": "Updated test rate",
            "verified_by": "Pytest",
        },
    )
    assert second.status_code == 201, second.text

    active_rates = client.get(
        "/api/rates",
        params={"metal": "gold", "active_only": "true"},
    )
    assert active_rates.status_code == 200
    assert len(active_rates.json()) == 1
    assert active_rates.json()[0]["id"] == second.json()["id"]

    history = client.get(
        "/api/rates",
        params={"metal": "gold", "active_only": "false"},
    )
    assert history.status_code == 200

    by_id = {item["id"]: item for item in history.json()}
    assert by_id[first.json()["id"]]["active"] is False
    assert by_id[second.json()["id"]]["active"] is True


def test_purchase_records_stock_and_initial_payment(client):
    product = create_product(client)

    response = client.post(
        "/api/purchases",
        headers=API_HEADERS,
        json=transaction_payload(
            product["id"],
            weight=10,
            rate=100,
            amount_paid=300,
            payment_method="cash",
        ),
    )

    assert response.status_code == 201, response.text
    purchase = response.json()
    assert purchase["kind"] == "purchase"
    assert Decimal(str(purchase["total_amount"])) == Decimal("1000")
    assert Decimal(str(purchase["amount_paid"])) == Decimal("300")

    payments = client.get(
        f"/api/transactions/{purchase['id']}/payments"
    )
    assert payments.status_code == 200, payments.text

    entries = payments.json()
    assert len(entries) == 1
    assert Decimal(str(entries[0]["amount"])) == Decimal("300")
    assert entries[0]["method"] == "cash"


def test_sale_reduces_stock_and_rejects_excess_sale(client):
    product = create_product(client)

    purchase = client.post(
        "/api/purchases",
        headers=API_HEADERS,
        json=transaction_payload(product["id"], weight=10),
    )
    assert purchase.status_code == 201, purchase.text

    sale = client.post(
        "/api/sales",
        headers=API_HEADERS,
        json=transaction_payload(product["id"], weight=4, rate=110),
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["kind"] == "sale"

    # Only 6 grams remain at Main Store.
    excessive_sale = client.post(
        "/api/sales",
        headers=API_HEADERS,
        json=transaction_payload(product["id"], weight=7, rate=110),
    )

    assert excessive_sale.status_code == 409
    assert "Insufficient stock" in excessive_sale.json()["detail"]


def test_invalid_weight_combination_is_rejected(client):
    product = create_product(client)

    payload = transaction_payload(product["id"], weight=5)
    payload["deduction_grams"] = 2
    payload["net_weight_grams"] = 4
    payload["quantity_grams"] = 4

    response = client.post(
        "/api/purchases",
        headers=API_HEADERS,
        json=payload,
    )

    assert response.status_code == 422


def test_payment_cannot_exceed_transaction_total(client):
    product = create_product(client)

    purchase = client.post(
        "/api/purchases",
        headers=API_HEADERS,
        json=transaction_payload(product["id"], weight=10, rate=100),
    )
    assert purchase.status_code == 201, purchase.text

    response = client.post(
        f"/api/transactions/{purchase.json()['id']}/payments",
        headers=API_HEADERS,
        json={
            "amount": 1001,
            "method": "cash",
            "note": "Overpayment test",
            "recorded_by": "Pytest",
        },
    )

    assert response.status_code == 422
