"""Idempotency: a retried checkout or payment must not record twice."""


from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _product(client: TestClient, headers: dict) -> dict:
    response = client.post(
        "/api/products",
        json={
            "sku": "IDEM-1",
            "name": "Idempotency gold",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 99.99,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _purchase(client: TestClient, headers: dict, product_id: int) -> dict:
    response = client.post(
        "/api/purchases",
        json={
            "product_id": product_id,
            "quantity_grams": 10,
            "gross_weight_grams": 10,
            "net_weight_grams": 10,
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": 3000,
            "rate_unit": "gram",
            "amount_paid": 30000,
            "location": "Main Store",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _sale_body(product_id: int, grams: str = "5") -> dict:
    # Rate is 3000/g at 100% purity, so the total is grams * 3000.
    # Pay half up front, which is always <= the total.
    total = int(grams) * 3000
    return {
        "product_id": product_id,
        "quantity_grams": grams,
        "gross_weight_grams": grams,
        "net_weight_grams": grams,
        "deduction_grams": 0,
        "purity": 100,
        "rate_per_gram": 3000,
        "rate_unit": "gram",
        "amount_paid": total // 2,
        "location": "Main Store",
    }


def test_duplicate_sale_with_same_key_records_once(
    client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")
    product = _product(client, admin)
    _purchase(client, admin, product["id"])

    body = _sale_body(product["id"])
    key = "idem-sale-key-1"
    headers = {**admin, "Idempotency-Key": key}

    first = client.post("/api/sales", json=body, headers=headers)
    assert first.status_code == 201
    first_ref = first.json()["reference"]

    # The retry (double-click / network resend) returns the SAME sale.
    second = client.post("/api/sales", json=body, headers=headers)
    assert second.status_code == 201
    assert second.json()["reference"] == first_ref

    # Only one sale exists for this product.
    sales = client.get("/api/sales", headers=admin).json()
    assert len(sales) == 1


def test_duplicate_batch_checkout_records_once(
    client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")
    product = _product(client, admin)
    _purchase(client, admin, product["id"])

    body = {"items": [_sale_body(product["id"], "3")]}
    key = "idem-batch-key-1"
    headers = {**admin, "Idempotency-Key": key}

    first = client.post("/api/sales/batch", json=body, headers=headers)
    assert first.status_code == 201
    first_refs = [r["reference"] for r in first.json()]

    second = client.post("/api/sales/batch", json=body, headers=headers)
    assert second.status_code == 201
    assert [r["reference"] for r in second.json()] == first_refs

    sales = client.get("/api/sales", headers=admin).json()
    assert len(sales) == 1


def test_duplicate_payment_with_same_key_records_once(
    client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")
    product = _product(client, admin)
    _purchase(client, admin, product["id"])
    sale = client.post(
        "/api/sales", json=_sale_body(product["id"], "10"), headers=admin
    ).json()

    body = {"amount": 5000, "method": "cash", "note": "idem payment"}
    key = "idem-pay-key-1"
    headers = {**admin, "Idempotency-Key": key}

    first = client.post(
        f"/api/transactions/{sale['id']}/payments",
        json=body,
        headers=headers,
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = client.post(
        f"/api/transactions/{sale['id']}/payments",
        json=body,
        headers=headers,
    )
    assert second.status_code == 201
    assert second.json()["id"] == first_id

    payments = client.get(
        f"/api/transactions/{sale['id']}/payments", headers=admin
    ).json()
    # The sale's initial payment (half up front) plus the ONE idempotent
    # payment. A non-deduplicated retry would have added a third.
    assert len(payments) == 2
    idem_payments = [p for p in payments if p["note"] == "idem payment"]
    assert len(idem_payments) == 1


def test_same_key_with_different_body_is_rejected(
    client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")
    product = _product(client, admin)
    _purchase(client, admin, product["id"])

    key = "idem-conflict-key"
    headers = {**admin, "Idempotency-Key": key}

    first = client.post(
        "/api/sales", json=_sale_body(product["id"], "1"), headers=headers
    )
    assert first.status_code == 201

    # Same key but a different amount: a client bug, so it is refused
    # rather than silently replaying an unrelated response.
    second = client.post(
        "/api/sales", json=_sale_body(product["id"], "2"), headers=headers
    )
    assert second.status_code == 422
    assert "different request body" in second.json()["detail"]


def test_no_key_still_allows_duplicate_requests(
    client: TestClient, db: Session, auth_headers
):
    """Without a header the endpoint behaves as before (two sales)."""
    admin = auth_headers("admin")
    product = _product(client, admin)
    _purchase(client, admin, product["id"])

    body = _sale_body(product["id"], "1")
    first = client.post("/api/sales", json=body, headers=admin)
    second = client.post("/api/sales", json=body, headers=admin)
    assert first.status_code == 201
    assert second.status_code == 201

    sales = client.get("/api/sales", headers=admin).json()
    assert len(sales) == 2


def test_failed_request_does_not_consume_the_key(
    client: TestClient, db: Session, auth_headers
):
    """An oversell rolls back the key claim, so a retry can succeed."""
    admin = auth_headers("admin")
    product = _product(client, admin)
    _purchase(client, admin, product["id"])

    key = "idem-oversell-key"
    headers = {**admin, "Idempotency-Key": key}

    # 10 g in stock; try to sell 50 g -> 409 insufficient stock.
    too_much = _sale_body(product["id"], "50")
    first = client.post("/api/sales", json=too_much, headers=headers)
    assert first.status_code == 409

    # The key was NOT consumed: the same key now sells the available 5 g.
    ok = _sale_body(product["id"], "5")
    retry = client.post("/api/sales", json=ok, headers=headers)
    assert retry.status_code == 201

    sales = client.get("/api/sales", headers=admin).json()
    assert len(sales) == 1


def test_purchase_duplicate_key_records_once(
    client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")
    product = _product(client, admin)

    body = {
        "product_id": product["id"],
        "quantity_grams": 5,
        "gross_weight_grams": 5,
        "net_weight_grams": 5,
        "deduction_grams": 0,
        "purity": 100,
        "rate_per_gram": 3000,
        "rate_unit": "gram",
        "amount_paid": 15000,
        "location": "Main Store",
    }
    key = "idem-purchase-key"
    headers = {**admin, "Idempotency-Key": key}

    first = client.post("/api/purchases", json=body, headers=headers)
    second = client.post("/api/purchases", json=body, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["reference"] == second.json()["reference"]

    purchases = client.get("/api/purchases", headers=admin).json()
    assert len(purchases) == 1
