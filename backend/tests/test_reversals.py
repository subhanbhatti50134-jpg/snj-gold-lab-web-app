from decimal import Decimal

from helpers import login_headers
from test_api import create_product, transaction_payload


def create_purchase(client, product_id, weight=10, amount_paid=0):
    payload = transaction_payload(
        product_id, weight=weight, rate=100, amount_paid=amount_paid
    )
    response = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_sale(client, product_id, weight=4):
    payload = transaction_payload(product_id, weight=weight, rate=100)
    response = client.post(
        "/api/sales",
        headers=login_headers(client, "operator"),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def cancel(client, transaction_id, reason="Entered by mistake", **extra):
    return client.post(
        f"/api/transactions/{transaction_id}/cancel",
        headers=login_headers(client, "manager"),
        json={"reason": reason, **extra},
    )


def stock_at(client, product_id, location="Main Store"):
    response = client.get(
        "/api/inventory",
        params={"location": location},
        headers=login_headers(client, "viewer"),
    )
    assert response.status_code == 200
    return sum(
        Decimal(str(row["balance_grams"]))
        for row in response.json()
        if row["product_id"] == product_id
    )


def test_cancel_purchase_restores_stock(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"], 10)
    assert stock_at(client, product["id"]) == Decimal("10")

    response = cancel(client, purchase["id"])
    assert response.status_code == 200, response.text

    record = response.json()
    assert record["status"] == "cancelled"
    assert record["cancelled_by"]
    assert record["cancel_reason"] == "Entered by mistake"
    # History is preserved, not deleted.
    assert record["reference"] == purchase["reference"]
    assert stock_at(client, product["id"]) == Decimal("0")


def test_cancel_sale_returns_stock_to_inventory(client):
    product = create_product(client)
    create_purchase(client, product["id"], 10)
    sale = create_sale(client, product["id"], 4)
    assert stock_at(client, product["id"]) == Decimal("6")

    response = cancel(client, sale["id"])
    assert response.status_code == 200, response.text
    assert stock_at(client, product["id"]) == Decimal("10")


def test_cancel_twice_is_rejected(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"], 5)

    assert cancel(client, purchase["id"]).status_code == 200
    second = cancel(client, purchase["id"])

    assert second.status_code == 409
    assert "already cancelled" in second.json()["detail"]


def test_cancel_requires_manager_role(client, auth_headers):
    product = create_product(client)
    purchase = create_purchase(client, product["id"], 5)

    headers = auth_headers("operator")
    response = client.post(
        f"/api/transactions/{purchase['id']}/cancel",
        headers=headers,
        json={"reason": "Not allowed"},
    )
    assert response.status_code == 403


def test_cancel_with_payments_needs_explicit_flag(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"], 10, amount_paid=300)

    blocked = cancel(client, purchase["id"])
    assert blocked.status_code == 409
    assert "include_payments=true" in blocked.json()["detail"]

    allowed = cancel(client, purchase["id"], include_payments=True)
    assert allowed.status_code == 200, allowed.text
    assert Decimal(str(allowed.json()["amount_paid"])) == Decimal("0")

    payments = client.get(
        f"/api/transactions/{purchase['id']}/payments",
        headers=login_headers(client, "operator"),
    ).json()
    amounts = [Decimal(str(p["amount"])) for p in payments]
    assert sum(amounts) == Decimal("0")


def test_cannot_pay_a_cancelled_transaction(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"], 10)
    assert cancel(client, purchase["id"]).status_code == 200

    response = client.post(
        f"/api/transactions/{purchase['id']}/payments",
        headers=login_headers(client, "operator"),
        json={"amount": 10, "method": "cash", "note": "", "recorded_by": "x"},
    )
    assert response.status_code == 409


def test_cancelled_sale_with_return_is_blocked(client):
    product = create_product(client)
    create_purchase(client, product["id"], 10)
    sale = create_sale(client, product["id"], 4)

    returned = client.post(
        "/api/movements/sales-returns",
        headers=login_headers(client, "manager"),
        json={
            "original_sale_id": sale["id"],
            "quantity_grams": 1,
            "created_by": "Pytest",
        },
    )
    assert returned.status_code == 201, returned.text

    response = cancel(client, sale["id"])
    assert response.status_code == 409
    assert "returns" in response.json()["detail"]


def test_cancelled_transaction_leaves_reports(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"], 10, amount_paid=500)
    assert cancel(client, purchase["id"], include_payments=True).status_code == 200

    summary = client.get(
        "/api/reports/summary",
        headers=login_headers(client, "viewer"),
    ).json()

    assert float(summary["purchase"]["total_amount"]) == 0
    assert float(summary["purchase"]["amount_paid"]) == 0

    history = client.get(
        "/api/transactions",
        params={"kind": "purchase"},
        headers=login_headers(client, "viewer"),
    ).json()
    assert all(row["id"] != purchase["id"] for row in history)

    with_cancelled = client.get(
        "/api/transactions",
        params={"kind": "purchase", "status": "cancelled"},
        headers=login_headers(client, "viewer"),
    ).json()
    assert any(row["id"] == purchase["id"] for row in with_cancelled)


def test_cancel_blocked_when_stock_already_sold(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"], 10)
    create_sale(client, product["id"], 8)

    # Only 2g left, but cancelling the 10g purchase would go to -8g.
    response = cancel(client, purchase["id"])
    assert response.status_code == 409
    assert "negative stock" in response.json()["detail"]
