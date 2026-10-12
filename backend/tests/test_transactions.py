from datetime import date

from test_api import API_HEADERS, create_product, transaction_payload


def create_purchase(client, product_id, weight=5):
    response = client.post(
        "/api/purchases",
        headers=API_HEADERS,
        json=transaction_payload(product_id, weight=weight, rate=100),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_transaction_history_requires_api_key(client):
    response = client.get("/api/transactions")
    assert response.status_code == 401


def test_transaction_history_lists_purchases(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"])

    response = client.get("/api/transactions", headers=API_HEADERS)

    assert response.status_code == 200, response.text
    assert any(item["id"] == purchase["id"] for item in response.json())


def test_transaction_history_filters_by_kind(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"])

    response = client.get(
        "/api/transactions",
        params={"kind": "purchase"},
        headers=API_HEADERS,
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
        headers=API_HEADERS,
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
        headers=API_HEADERS,
    )

    assert response.status_code == 422
