from decimal import Decimal

from helpers import login_headers
from test_api import create_product, transaction_payload


def create_purchase(client, product_id, weight=10, location="Main Store"):
    payload = transaction_payload(product_id, weight=weight, rate=100)
    payload["location"] = location

    response = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def transfer(client, product_id, weight, from_location, to_location):
    return client.post(
        "/api/movements/transfers",
        headers=login_headers(client, "manager"),
        json={
            "product_id": product_id,
            "quantity_grams": weight,
            "from_location": from_location,
            "to_location": to_location,
            "created_by": "Pytest",
            "notes": "Test transfer",
        },
    )


def balances(client, product_id):
    response = client.get(
        "/api/inventory",
        headers=login_headers(client, "viewer"),
    )
    assert response.status_code == 200, response.text
    return {
        row["location"]: Decimal(str(row["balance_grams"]))
        for row in response.json()
        if row["product_id"] == product_id
    }


def test_transfer_moves_stock_without_changing_total(client):
    product = create_product(client)
    create_purchase(client, product["id"], 10)

    response = transfer(client, product["id"], 4, "Main Store", "Annex")
    assert response.status_code == 201, response.text

    record = response.json()
    assert record["kind"] == "stock_transfer"
    assert record["location"] == "Main Store"
    assert record["destination"] == "Annex"
    assert Decimal(str(record["total_amount"])) == 0

    stock = balances(client, product["id"])
    assert stock["Main Store"] == Decimal("6")
    assert stock["Annex"] == Decimal("4")
    # Total is unchanged: transfers never create or destroy stock.
    assert sum(stock.values()) == Decimal("10")


def test_transfer_cannot_exceed_source_stock(client):
    product = create_product(client)
    create_purchase(client, product["id"], 5)

    response = transfer(client, product["id"], 6, "Main Store", "Annex")

    assert response.status_code == 409
    assert "Transfer exceeds available stock" in response.json()["detail"]


def test_transfer_requires_different_locations(client):
    product = create_product(client)
    create_purchase(client, product["id"], 5)

    response = transfer(client, product["id"], 1, "Main Store", "Main Store")
    assert response.status_code == 422


def test_transfer_requires_manager_role(client, auth_headers):
    headers = auth_headers("operator")
    response = client.post(
        "/api/movements/transfers",
        headers=headers,
        json={
            "product_id": 1,
            "quantity_grams": 1,
            "from_location": "A",
            "to_location": "B",
            "created_by": "Pytest",
        },
    )
    assert response.status_code == 403


def test_transfer_requires_login(client):
    response = client.post(
        "/api/movements/transfers",
        json={
            "product_id": 1,
            "quantity_grams": 1,
            "from_location": "A",
            "to_location": "B",
            "created_by": "Pytest",
        },
    )
    assert response.status_code == 401
