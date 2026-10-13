from decimal import Decimal

from helpers import login_headers
from test_api import create_product, transaction_payload


def get_dashboard(client):
    response = client.get(
        "/api/dashboard", headers=login_headers(client, "viewer")
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_dashboard_requires_login(client):
    assert client.get("/api/dashboard").status_code == 401


def test_dashboard_is_empty_on_fresh_database(client):
    data = get_dashboard(client)
    assert float(data["stock_grams"]) == 0
    assert float(data["inventory_value"]) == 0
    assert data["product_count"] == 0
    assert data["recent_transactions"] == []


def test_dashboard_totals_follow_transactions(client):
    # A rate matching the product purity, plus stock, so valuation runs.
    rate = client.post(
        "/api/rates",
        headers=login_headers(client, "manager"),
        json={
            "metal": "gold",
            "purity": 100,
            "rate_per_gram": 200,
            "unit": "gram",
            "verified_by": "Pytest",
        },
    )
    assert rate.status_code == 201, rate.text

    product = create_product(client)

    purchase = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=transaction_payload(
            product["id"], weight=10, rate=200, amount_paid=500
        ),
    )
    assert purchase.status_code == 201, purchase.text

    sale = client.post(
        "/api/sales",
        headers=login_headers(client, "operator"),
        json=transaction_payload(product["id"], weight=4, rate=200),
    )
    assert sale.status_code == 201, sale.text

    data = get_dashboard(client)

    assert Decimal(str(data["stock_grams"])) == Decimal("6")
    # 6 grams left at 200/g = 1200.
    assert Decimal(str(data["inventory_value"])) == Decimal("1200.00")
    assert data["product_count"] == 1
    assert data["transaction_count"] == 2
    assert Decimal(str(data["purchases"]["total_amount"])) == Decimal("2000.00")
    assert Decimal(str(data["sales"]["total_amount"])) == Decimal("800.00")
    assert len(data["recent_transactions"]) == 2


def test_dashboard_lists_unvalued_products(client):
    product = create_product(client, sku="NO-RATE-001")

    client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=transaction_payload(
            product["id"], weight=3, rate=100, amount_paid=0
        ),
    )

    data = get_dashboard(client)
    assert data["unvalued_products"]
    assert data["unvalued_products"][0]["product_id"] == product["id"]
    assert float(data["inventory_value"]) == 0
