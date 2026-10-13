from helpers import login_headers
from test_api import create_product, transaction_payload


def create_transaction(client, kind, product_id, weight=5, amount_paid=0):
    payload = transaction_payload(
        product_id,
        weight=weight,
        rate=100,
        amount_paid=amount_paid,
    )
    response = client.post(
        f"/api/{kind}s",
        headers=login_headers(client, "operator"),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_cashflow_requires_login(client):
    response = client.get("/api/reports/cashflow")
    assert response.status_code == 401


def test_cashflow_reports_sale_received_and_purchase_paid(client):
    product = create_product(client)
    create_transaction(client, "purchase", product["id"], amount_paid=200)
    create_transaction(client, "sale", product["id"], amount_paid=300)

    response = client.get(
        "/api/reports/cashflow",
        headers=login_headers(client, "viewer"),
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert float(data["money_received"]) == 300
    assert float(data["money_paid"]) == 200
    assert float(data["net_cashflow"]) == 100
    assert data["payment_count"] == 2


def test_cashflow_filters_by_payment_method(client):
    product = create_product(client)
    create_transaction(client, "purchase", product["id"], amount_paid=200)

    response = client.get(
        "/api/reports/cashflow",
        params={"method": "cash"},
        headers=login_headers(client, "viewer"),
    )
    assert response.status_code == 200, response.text
    assert float(response.json()["money_paid"]) == 200


def test_cashflow_rejects_invalid_date_range(client):
    response = client.get(
        "/api/reports/cashflow",
        params={
            "date_from": "2026-10-12",
            "date_to": "2026-10-01",
        },
        headers=login_headers(client, "viewer"),
    )
    assert response.status_code == 422


def test_cashflow_pagination(client):
    product = create_product(client)
    create_transaction(client, "purchase", product["id"], amount_paid=100)
    create_transaction(client, "purchase", product["id"], amount_paid=200)

    response = client.get(
        "/api/reports/cashflow",
        params={"skip": 0, "limit": 1},
        headers=login_headers(client, "viewer"),
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["payment_count"] == 2
    assert len(data["items"]) == 1
