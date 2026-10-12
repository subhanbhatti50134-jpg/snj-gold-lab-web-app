from helpers import login_headers
from test_api import create_product, transaction_payload
from test_movements import create_purchase


def _post_transaction(client, url, role):
    product = create_product(client)
    payload = transaction_payload(product["id"], weight=5, rate=100)
    payload["created_by"] = "Someone Else"
    return client.post(url, json=payload, headers=login_headers(client, role))


def test_purchase_created_by_comes_from_token(client):
    response = _post_transaction(client, "/api/purchases", "operator")
    assert response.status_code == 201, response.text
    assert response.json()["created_by"] == "test_operator"


def test_sale_created_by_comes_from_token(client):
    product = create_product(client)
    create_purchase(client, product["id"], 10)
    payload = transaction_payload(product["id"], weight=2, rate=100)
    payload["created_by"] = "Someone Else"
    response = client.post(
        "/api/sales",
        json=payload,
        headers=login_headers(client, "operator"),
    )
    assert response.status_code == 201, response.text
    assert response.json()["created_by"] == "test_operator"


def test_adjustment_created_by_comes_from_token(client):
    product = create_product(client)
    create_purchase(client, product["id"], 5)
    response = client.post(
        "/api/movements/adjustments",
        headers=login_headers(client, "manager"),
        json={
            "product_id": product["id"],
            "direction": "increase",
            "quantity_grams": 0.5,
            "location": "Main Store",
            "reason": "Physical stock correction",
            "created_by": "Someone Else",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["created_by"] == "test_manager"


def test_payment_recorded_by_comes_from_token(client):
    product = create_product(client)
    payload = transaction_payload(product["id"], weight=5, rate=100)
    purchase = client.post(
        "/api/purchases",
        json=payload,
        headers=login_headers(client, "operator"),
    )
    assert purchase.status_code == 201, purchase.text

    response = client.post(
        f"/api/transactions/{purchase.json()['id']}/payments",
        json={"amount": 1, "method": "cash", "recorded_by": "Someone Else"},
        headers=login_headers(client, "manager"),
    )
    assert response.status_code == 201, response.text
    assert response.json()["recorded_by"] == "test_manager"
