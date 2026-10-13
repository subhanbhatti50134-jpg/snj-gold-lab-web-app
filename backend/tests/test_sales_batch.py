from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def make_product(
    client: TestClient, headers: dict, sku: str, name: str
) -> dict:
    response = client.post(
        "/api/products",
        json={
            "sku": sku,
            "name": name,
            "category": "loose_metal",
            "metal": "gold",
            "purity": 100,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def stock_in(db: Session, product_id: int, location: str = "Main Store"):
    from app.services.inventory import get_stock_balance

    return get_stock_balance(db, product_id, location)


def item(product_id: int, grams: float, rate: float, paid: float) -> dict:
    return {
        "product_id": product_id,
        "quantity_grams": grams,
        "gross_weight_grams": grams,
        "net_weight_grams": grams,
        "deduction_grams": 0,
        "purity": 100,
        "rate_per_gram": rate,
        "rate_unit": "gram",
        "amount_paid": paid,
        "location": "Main Store",
    }


def test_batch_checkout_creates_all_sales(
    client: TestClient, db: Session, auth_headers
):
    headers = auth_headers("manager")
    product = make_product(client, headers, "POS-1", "POS gold")

    # Fund the stock with a purchase first.
    client.post(
        "/api/purchases",
        json=item(product["id"], 50, 2000, 100000),
        headers=headers,
    )

    before = stock_in(db, product["id"])

    response = client.post(
        "/api/sales/batch",
        json={
            "items": [
                item(product["id"], 5, 3000, 15000),
                item(product["id"], 10, 3000, 30000),
            ]
        },
        headers=headers,
    )
    assert response.status_code == 201

    rows = response.json()
    assert len(rows) == 2
    assert all(row["kind"] == "sale" for row in rows)
    assert float(rows[0]["total_amount"]) == 15000
    assert float(rows[1]["total_amount"]) == 30000

    # Both lines hit the stock exactly once each.
    after = stock_in(db, product["id"])
    assert float(before) - float(after) == 15


def test_batch_is_atomic_on_failure(
    client: TestClient, db: Session, auth_headers
):
    headers = auth_headers("manager")
    product = make_product(client, headers, "POS-2", "POS atomic gold")

    # Only 10 g in stock.
    client.post(
        "/api/purchases",
        json=item(product["id"], 10, 2000, 20000),
        headers=headers,
    )

    before = stock_in(db, product["id"])
    before_sales = len(
        [
            t
            for t in client.get("/api/sales", headers=headers).json()
            if t["product_id"] == product["id"]
        ]
    )

    # First line would succeed, second line oversells -> nothing saved.
    response = client.post(
        "/api/sales/batch",
        json={
            "items": [
                item(product["id"], 5, 3000, 15000),
                item(product["id"], 100, 3000, 300000),
            ]
        },
        headers=headers,
    )
    assert response.status_code == 409

    after_sales = [
        t
        for t in client.get("/api/sales", headers=headers).json()
        if t["product_id"] == product["id"]
    ]
    assert len(after_sales) == before_sales
    assert float(stock_in(db, product["id"])) == float(before)


def test_batch_rejects_empty_items(
    client: TestClient, db: Session, auth_headers
):
    response = client.post(
        "/api/sales/batch",
        json={"items": []},
        headers=auth_headers("manager"),
    )
    assert response.status_code == 422


def test_batch_forbidden_for_viewer(
    client: TestClient, db: Session, auth_headers
):
    response = client.post(
        "/api/sales/batch",
        json={"items": []},
        headers=auth_headers("viewer"),
    )
    # Role check runs before body validation.
    assert response.status_code == 403
