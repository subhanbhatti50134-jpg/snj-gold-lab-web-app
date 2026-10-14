from datetime import date
from decimal import Decimal

from helpers import login_headers
from test_api import create_product, transaction_payload


def create_purchase(client, product_id, weight=5):
    response = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=transaction_payload(product_id, weight=weight, rate=100),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_transaction_history_requires_login(client):
    response = client.get("/api/transactions")
    assert response.status_code == 401


def test_transaction_history_lists_purchases(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"])

    response = client.get("/api/transactions", headers=login_headers(client, "viewer"))

    assert response.status_code == 200, response.text
    assert any(item["id"] == purchase["id"] for item in response.json())


def test_transaction_history_filters_by_kind(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"])

    response = client.get(
        "/api/transactions",
        params={"kind": "purchase"},
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 200, response.text
    assert all(item["kind"] == "purchase" for item in response.json())
    assert any(item["id"] == purchase["id"] for item in response.json())


def test_transaction_history_pagination(client):
    product = create_product(client)
    create_purchase(client, product["id"], 2)
    create_purchase(client, product["id"], 3)

    response = client.get(
        "/api/transactions",
        params={"skip": 0, "limit": 1},
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1


def test_transaction_history_rejects_invalid_date_range(client):
    response = client.get(
        "/api/transactions",
        params={
            "date_from": date(2026, 10, 12).isoformat(),
            "date_to": date(2026, 10, 1).isoformat(),
        },
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 422


def test_transaction_detail_requires_login(client):
    assert client.get("/api/transactions/1").status_code == 401


def test_transaction_detail_not_found(client):
    response = client.get("/api/transactions/999999", headers=login_headers(client, "viewer"))
    assert response.status_code == 404


def test_transaction_detail_includes_receipt_data(client):
    product = create_product(client)
    purchase = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=transaction_payload(product["id"], weight=10, rate=100, amount_paid=400),
    )
    assert purchase.status_code == 201, purchase.text

    response = client.get(
        f"/api/transactions/{purchase.json()['id']}",
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["product_name"] == product["name"]
    assert body["product_sku"] == product["sku"]
    assert Decimal(str(body["paid_total"])) == Decimal("400")
    assert Decimal(str(body["due_amount"])) == Decimal("600")
    assert len(body["payments"]) == 1
    assert Decimal(str(body["payments"][0]["amount"])) == Decimal("400")
    assert body["business"]["name"] == "Saleem Nadeem Jewellers"
    assert "currency" in body["business"]


def test_transaction_detail_tracks_later_payments(client):
    product = create_product(client)
    create_purchase(client, product["id"], 5)
    sale = client.post(
        "/api/sales",
        headers=login_headers(client, "operator"),
        json=transaction_payload(product["id"], weight=5, rate=100, amount_paid=100),
    )
    assert sale.status_code == 201, sale.text
    sale_id = sale.json()["id"]

    pay = client.post(
        f"/api/transactions/{sale_id}/payments",
        headers=login_headers(client, "operator"),
        json={"amount": 250, "method": "cash", "note": "part payment"},
    )
    assert pay.status_code == 201, pay.text

    response = client.get(
        f"/api/transactions/{sale_id}",
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(str(body["paid_total"])) == Decimal("350")
    assert Decimal(str(body["due_amount"])) == Decimal("150")
    assert len(body["payments"]) == 2
