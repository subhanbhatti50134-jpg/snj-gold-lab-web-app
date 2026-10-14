from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product import Product


def make_product(db: Session) -> Product:
    product = Product(
        sku="PROF-1",
        name="Profit test gold",
        category="loose_metal",
        metal="gold",
        purity=99.99,
        active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def test_profit_report(client: TestClient, db: Session, auth_headers):
    product = make_product(db)

    # Purchase 10 g @ 2000/g at 100% purity = 20000
    response = client.post(
        "/api/purchases",
        json={
            "product_id": product.id,
            "quantity_grams": 10,
            "gross_weight_grams": 10,
            "net_weight_grams": 10,
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": 2000,
            "rate_unit": "gram",
            "amount_paid": 20000,
            "location": "Main Store",
        },
        headers=auth_headers("manager"),
    )
    assert response.status_code == 201

    # Sale 4 g @ 3000/g at 100% purity = 12000
    response = client.post(
        "/api/sales",
        json={
            "product_id": product.id,
            "quantity_grams": 4,
            "gross_weight_grams": 4,
            "net_weight_grams": 4,
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": 3000,
            "rate_unit": "gram",
            "amount_paid": 12000,
            "location": "Main Store",
        },
        headers=auth_headers("manager"),
    )
    assert response.status_code == 201

    response = client.get("/api/reports/profit", headers=auth_headers("manager"))
    assert response.status_code == 200

    data = response.json()
    assert data["is_estimate"] is True
    assert float(data["purchases_total"]) == 20000
    assert float(data["sales_total"]) == 12000
    # Estimated profit = sales - returns - purchases = 12000 - 0 - 20000
    assert float(data["estimated_profit"]) == -8000
    assert "not a precise" in data["note"].lower()


def test_transaction_date_filter(client: TestClient, db: Session, auth_headers):
    product = make_product(db)

    # Create a purchase with a specific transaction date
    response = client.post(
        "/api/purchases",
        json={
            "product_id": product.id,
            "quantity_grams": 10,
            "gross_weight_grams": 10,
            "net_weight_grams": 10,
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": 2000,
            "rate_unit": "gram",
            "amount_paid": 20000,
            "location": "Main Store",
            "transaction_date": "2026-01-15",
        },
        headers=auth_headers("manager"),
    )
    assert response.status_code == 201
    tx_id = response.json()["id"]
    assert response.json()["transaction_date"] == "2026-01-15"

    # Filter by date range that includes 2026-01-15
    response = client.get(
        "/api/transactions?date_from=2026-01-01&date_to=2026-01-31",
        headers=auth_headers("manager"),
    )
    assert response.status_code == 200
    txs = response.json()
    ids = [tx["id"] for tx in txs]
    assert tx_id in ids
    # The list endpoint exposes transaction_date too
    assert any(tx["transaction_date"] == "2026-01-15" for tx in txs)

    # Filter by a range that does NOT include it
    response = client.get(
        "/api/transactions?date_from=2026-02-01&date_to=2026-02-28",
        headers=auth_headers("manager"),
    )
    assert response.status_code == 200
    ids = [tx["id"] for tx in response.json()]
    assert tx_id not in ids


def test_transaction_date_defaults_to_today(
    client: TestClient, db: Session, auth_headers
):
    product = make_product(db)

    response = client.post(
        "/api/purchases",
        json={
            "product_id": product.id,
            "quantity_grams": 10,
            "gross_weight_grams": 10,
            "net_weight_grams": 10,
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": 2000,
            "rate_unit": "gram",
            "amount_paid": 20000,
            "location": "Main Store",
        },
        headers=auth_headers("manager"),
    )
    assert response.status_code == 201
    tx = response.json()
    assert tx["transaction_date"] is not None
    # The service defaults it to today's date when the client omits it.
    assert tx["transaction_date"] == date.today().isoformat()
