from decimal import Decimal

from helpers import login_headers
from test_api import create_product
from test_reports import create_purchase

ORDER = {
    "party_name": "Bayana Customer",
    "description": "Custom necklace",
    "estimated_weight_grams": 2,
    "agreed_rate_per_gram": 24000,
    "advance_amount": 10000,
    "due_date": "2026-11-01",
}


def make_order(client, role="operator", **overrides):
    payload = {**ORDER, **overrides}
    return client.post(
        "/api/orders",
        headers=login_headers(client, role),
        json=payload,
    )


def test_orders_require_login(client):
    assert client.get("/api/orders").status_code == 401
    assert client.post("/api/orders", json=ORDER).status_code == 401


def test_create_order_computes_totals_and_balance(client):
    response = make_order(client)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["reference"].startswith("ORD-")
    assert row["status"] == "pending"
    # 2g x 24000 = 48000 estimate, 10000 paid as bayana
    assert Decimal(row["estimated_total"]) == Decimal("48000")
    assert Decimal(row["advance_amount"]) == Decimal("10000")
    assert Decimal(row["balance"]) == Decimal("38000")


def test_create_order_requires_party(client):
    response = make_order(client, party_name="   ")
    assert response.status_code == 422, response.text


def test_advance_cannot_exceed_estimate(client):
    response = make_order(client, advance_amount=999999)
    assert response.status_code == 422, response.text
    assert "Advance" in response.json()["detail"]


def test_viewer_cannot_create_order(client):
    response = make_order(client, role="viewer")
    assert response.status_code == 403


def test_advance_top_up_and_cap(client):
    created = make_order(client)
    order_id = created.json()["id"]

    response = client.post(
        f"/api/orders/{order_id}/advance",
        headers=login_headers(client, "operator"),
        json={"amount": 20000},
    )
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["advance_amount"]) == Decimal("30000")
    assert Decimal(response.json()["balance"]) == Decimal("18000")

    over = client.post(
        f"/api/orders/{order_id}/advance",
        headers=login_headers(client, "operator"),
        json={"amount": 100000},
    )
    assert over.status_code == 422, over.text


def test_advance_is_idempotent(client):
    created = make_order(client)
    order_id = created.json()["id"]
    headers = login_headers(client, "operator")
    headers["Idempotency-Key"] = "bayana-advance-1"

    first = client.post(
        f"/api/orders/{order_id}/advance",
        headers=headers,
        json={"amount": 5000},
    )
    second = client.post(
        f"/api/orders/{order_id}/advance",
        headers=headers,
        json={"amount": 5000},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    # The replay returns the first result; only one advance is applied.
    assert Decimal(second.json()["advance_amount"]) == Decimal("15000")


def test_deliver_creates_sale_with_advance(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)
    created = make_order(client)
    order_id = created.json()["id"]

    response = client.post(
        f"/api/orders/{order_id}/deliver",
        headers=login_headers(client, "operator"),
        json={"product_id": product["id"]},
    )
    assert response.status_code == 201, response.text
    sale = response.json()
    assert sale["reference"].startswith("SAL-")
    # 2g x 24000, advance applied as amount paid
    assert Decimal(sale["total_amount"]) == Decimal("48000")
    assert Decimal(sale["amount_paid"]) == Decimal("10000")
    assert sale["party_name"] == "Bayana Customer"

    order = client.get(
        f"/api/orders/{order_id}", headers=login_headers(client, "viewer")
    ).json()
    assert order["status"] == "delivered"
    assert order["sale_id"] == sale["id"]


def test_deliver_weight_override_changes_total(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)
    created = make_order(client)

    response = client.post(
        f"/api/orders/{created.json()['id']}/deliver",
        headers=login_headers(client, "operator"),
        json={"product_id": product["id"], "actual_weight_grams": 1.5},
    )
    assert response.status_code == 201, response.text
    # 1.5g x 24000 = 36000; advance 10000 still applied
    assert Decimal(response.json()["total_amount"]) == Decimal("36000")
    assert Decimal(response.json()["amount_paid"]) == Decimal("10000")


def test_deliver_twice_conflicts(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)
    created = make_order(client)
    order_id = created.json()["id"]

    first = client.post(
        f"/api/orders/{order_id}/deliver",
        headers=login_headers(client, "operator"),
        json={"product_id": product["id"]},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        f"/api/orders/{order_id}/deliver",
        headers=login_headers(client, "operator"),
        json={"product_id": product["id"]},
    )
    assert second.status_code == 409, second.text


def test_deliver_without_stock_keeps_order_pending(client):
    product = create_product(client)
    created = make_order(client)

    response = client.post(
        f"/api/orders/{created.json()['id']}/deliver",
        headers=login_headers(client, "operator"),
        json={"product_id": product["id"]},
    )
    assert response.status_code == 409, response.text

    order = client.get(
        f"/api/orders/{created.json()['id']}",
        headers=login_headers(client, "viewer"),
    ).json()
    assert order["status"] == "pending"
    assert order["sale_id"] is None


def test_cancel_then_cannot_deliver(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)
    created = make_order(client)
    order_id = created.json()["id"]

    cancelled = client.post(
        f"/api/orders/{order_id}/cancel",
        headers=login_headers(client, "manager"),
        json={"reason": "Customer changed mind"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    response = client.post(
        f"/api/orders/{order_id}/deliver",
        headers=login_headers(client, "operator"),
        json={"product_id": product["id"]},
    )
    assert response.status_code == 409, response.text


def test_operator_cannot_cancel(client):
    created = make_order(client)
    response = client.post(
        f"/api/orders/{created.json()['id']}/cancel",
        headers=login_headers(client, "operator"),
        json={},
    )
    assert response.status_code == 403


def test_edit_pending_order_recomputes_terms(client):
    created = make_order(client)
    order_id = created.json()["id"]

    response = client.patch(
        f"/api/orders/{order_id}",
        headers=login_headers(client, "manager"),
        json={
            "description": "Bigger necklace",
            "estimated_weight_grams": 3,
            "agreed_rate_per_gram": 25000,
            "due_date": "2026-12-01",
            "notes": "Urgent",
        },
    )
    assert response.status_code == 200, response.text
    row = response.json()
    assert Decimal(row["estimated_total"]) == Decimal("75000")
    assert Decimal(row["balance"]) == Decimal("65000")


def test_edit_cannot_drop_below_advance(client):
    created = make_order(client)

    response = client.patch(
        f"/api/orders/{created.json()['id']}",
        headers=login_headers(client, "manager"),
        json={
            "description": "Tiny ring",
            "estimated_weight_grams": 1,
            "agreed_rate_per_gram": 100,
            "due_date": None,
            "notes": "",
        },
    )
    assert response.status_code == 422, response.text


def test_delivered_order_cannot_be_edited(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)
    created = make_order(client)
    order_id = created.json()["id"]
    client.post(
        f"/api/orders/{order_id}/deliver",
        headers=login_headers(client, "operator"),
        json={"product_id": product["id"]},
    )

    response = client.patch(
        f"/api/orders/{order_id}",
        headers=login_headers(client, "manager"),
        json={
            "description": "Changed",
            "estimated_weight_grams": 2,
            "agreed_rate_per_gram": 24000,
            "due_date": None,
            "notes": "",
        },
    )
    assert response.status_code == 409, response.text


def test_list_orders_filters_by_status(client):
    make_order(client)
    pending = client.get(
        "/api/orders?status=pending", headers=login_headers(client, "viewer")
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()

    delivered = client.get(
        "/api/orders?status=delivered", headers=login_headers(client, "viewer")
    )
    assert delivered.status_code == 200
    assert delivered.json() == [] or all(
        row["status"] == "delivered" for row in delivered.json()
    )
