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


def transaction_payload(product_id, weight, rate=100):
    return {
        "product_id": product_id,
        "quantity_grams": weight,
        "gross_weight_grams": weight,
        "net_weight_grams": weight,
        "deduction_grams": 0,
        "purity": 100,
        "rate_per_gram": rate,
        "charges": 0,
        "amount_paid": 0,
        "payment_method": "cash",
        "party_name": "Test Customer",
        "location": "Main Store",
        "created_by": "Pytest",
    }


def create_purchase(client, product_id, weight=10):
    response = client.post(
        "/api/purchases",
        headers=API_HEADERS,
        json=transaction_payload(product_id, weight),
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_sale(client, product_id, weight=4):
    response = client.post(
        "/api/sales",
        headers=API_HEADERS,
        json=transaction_payload(product_id, weight),
    )
    assert response.status_code == 201, response.text
    return response.json()


def inventory_balance(client, product_id, location="Main Store"):
    response = client.get(
        "/api/inventory",
        params={"location": location},
        headers=login_headers(client, "viewer"),
    )
    assert response.status_code == 200, response.text
    return sum(
        Decimal(str(item["balance_grams"]))
        for item in response.json()
        if item["product_id"] == product_id
    )


def test_sales_return_adds_stock_and_links_original_sale(client):
    product = create_product(client)
    create_purchase(client, product["id"], 10)
    sale = create_sale(client, product["id"], 4)

    response = client.post(
        "/api/movements/sales-returns",
        headers=API_HEADERS,
        json={
            "original_sale_id": sale["id"],
            "quantity_grams": 1,
            "created_by": "Pytest",
            "notes": "Test return",
        },
    )

    assert response.status_code == 201, response.text
    returned = response.json()
    assert returned["kind"] == "sales_return"
    assert returned["destination"] == sale["reference"]
    assert Decimal(str(returned["quantity_grams"])) == Decimal("1")
    assert inventory_balance(client, product["id"]) == Decimal("7")


def test_sales_return_cannot_exceed_original_sale_quantity(client):
    product = create_product(client)
    create_purchase(client, product["id"], 10)
    sale = create_sale(client, product["id"], 4)

    first = client.post(
        "/api/movements/sales-returns",
        headers=API_HEADERS,
        json={
            "original_sale_id": sale["id"],
            "quantity_grams": 3,
            "created_by": "Pytest",
        },
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/movements/sales-returns",
        headers=API_HEADERS,
        json={
            "original_sale_id": sale["id"],
            "quantity_grams": 2,
            "created_by": "Pytest",
        },
    )
    assert second.status_code == 409, second.text
    assert inventory_balance(client, product["id"]) == Decimal("9")


def test_return_requires_a_real_sale(client):
    response = client.post(
        "/api/movements/sales-returns",
        headers=API_HEADERS,
        json={
            "original_sale_id": 99999,
            "quantity_grams": 1,
            "created_by": "Pytest",
        },
    )
    assert response.status_code == 404, response.text


def test_stock_increase_adjustment_updates_inventory(client):
    product = create_product(client)
    create_purchase(client, product["id"], 5)

    response = client.post(
        "/api/movements/adjustments",
        headers=API_HEADERS,
        json={
            "product_id": product["id"],
            "direction": "increase",
            "quantity_grams": 0.5,
            "location": "Main Store",
            "reason": "Physical stock correction",
            "created_by": "Pytest",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["kind"] == "stock_adjustment"
    assert inventory_balance(client, product["id"]) == Decimal("5.5000")


def test_stock_decrease_adjustment_updates_inventory(client):
    product = create_product(client)
    create_purchase(client, product["id"], 5)

    response = client.post(
        "/api/movements/adjustments",
        headers=API_HEADERS,
        json={
            "product_id": product["id"],
            "direction": "decrease",
            "quantity_grams": 2,
            "location": "Main Store",
            "reason": "Physical stock correction",
            "created_by": "Pytest",
        },
    )

    assert response.status_code == 201, response.text
    assert inventory_balance(client, product["id"]) == Decimal("3.0000")


def test_stock_decrease_cannot_exceed_available_stock(client):
    product = create_product(client)
    create_purchase(client, product["id"], 2)

    response = client.post(
        "/api/movements/adjustments",
        headers=API_HEADERS,
        json={
            "product_id": product["id"],
            "direction": "decrease",
            "quantity_grams": 3,
            "location": "Main Store",
            "reason": "Excess decrease test",
            "created_by": "Pytest",
        },
    )

    assert response.status_code == 409, response.text
    assert inventory_balance(client, product["id"]) == Decimal("2.0000")


def test_movement_write_endpoints_require_api_key(client):
    return_response = client.post(
        "/api/movements/sales-returns",
        json={
            "original_sale_id": 1,
            "quantity_grams": 1,
            "created_by": "Pytest",
        },
    )
    adjustment_response = client.post(
        "/api/movements/adjustments",
        json={
            "product_id": 1,
            "direction": "increase",
            "quantity_grams": 1,
            "reason": "Test",
            "created_by": "Pytest",
        },
    )

    assert return_response.status_code == 401
    assert adjustment_response.status_code == 401
