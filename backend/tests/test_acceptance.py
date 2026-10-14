"""Acceptance tests: complete business journeys through the real API.

Unlike the unit tests, each test here walks through a scenario a shop
owner would recognise end to end — catalog, rates, purchase, sale,
payment, return, cancellation, reports — asserting the business rules
hold at every step.
"""

from decimal import Decimal

from helpers import login_headers
from test_api import create_product, transaction_payload


def create_party(client, name, kind):
    response = client.post(
        "/api/parties",
        headers=login_headers(client, "manager"),
        json={"name": name, "kind": kind, "phone": "0300-0000000"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def post_transaction(client, kind, product_id, weight, rate, party_id=None, **extra):
    payload = transaction_payload(product_id, weight=weight, rate=rate, **extra)
    if party_id is not None:
        payload["party_id"] = party_id
        payload.pop("party_name")
    response = client.post(
        f"/api/{kind}s",
        headers=login_headers(client, "operator"),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def stock(client, product_id):
    response = client.get(
        "/api/inventory",
        headers=login_headers(client, "viewer"),
    )
    assert response.status_code == 200
    return sum(
        Decimal(str(row["balance_grams"]))
        for row in response.json()
        if row["product_id"] == product_id
    )


def party_by_name(client, name):
    rows = client.get("/api/parties", headers=login_headers(client, "viewer")).json()
    return next(row for row in rows if row["name"] == name)


def test_full_trading_day(client):
    """Catalog → purchase (partial payment) → sale → settlement → profit."""
    product = create_product(client, sku="ACC-GOLD")
    supplier = create_party(client, "Karachi Metals", "supplier")
    customer = create_party(client, "Ashraf Jewellers", "customer")

    # Stock in: 10 g at 100/g; pay 500 of the 1000 immediately.
    post_transaction(
        client, "purchase", product["id"], 10, 100,
        party_id=supplier["id"], amount_paid=500,
    )
    assert Decimal(str(stock(client, product["id"]))) == Decimal("10")
    assert Decimal(str(party_by_name(client, "Karachi Metals")["payable"])) == Decimal("500")

    # Sale: 4 g at 150/g = 600, nothing paid yet.
    sale = post_transaction(
        client, "sale", product["id"], 4, 150,
        party_id=customer["id"], amount_paid=0,
    )
    assert Decimal(str(stock(client, product["id"]))) == Decimal("6")
    assert Decimal(str(party_by_name(client, "Ashraf Jewellers")["receivable"])) == Decimal("600")

    # Customer settles the full 600.
    payment = client.post(
        f"/api/transactions/{sale['id']}/payments",
        headers=login_headers(client, "operator"),
        json={"amount": "600", "method": "cash", "note": "full settlement"},
    )
    assert payment.status_code == 201, payment.text
    assert Decimal(str(party_by_name(client, "Ashraf Jewellers")["receivable"])) == Decimal("0")

    # The profit report is a documented sales-minus-purchases estimate.
    profit = client.get(
        "/api/reports/profit",
        headers=login_headers(client, "viewer"),
    )
    assert profit.status_code == 200, profit.text
    body = profit.json()
    assert Decimal(str(body["sales_total"])) == Decimal("600")
    assert Decimal(str(body["purchases_total"])) == Decimal("1000")
    assert Decimal(str(body["estimated_profit"])) == (
        Decimal(str(body["sales_total"]))
        - Decimal(str(body["purchases_total"]))
        - Decimal(str(body["sales_returns_value"]))
    )
    assert body["is_estimate"] is True

    # Every step left an audit trail.
    audit = client.get("/api/audit", headers=login_headers(client, "admin")).json()
    actions = {entry["action"] for entry in audit}
    assert "product.create" in actions
    assert "purchase.create" in actions
    assert "sale.create" in actions
    assert "payment.create" in actions


def test_sales_return_journey(client):
    """Returned goods come back to stock and lower the customer's dues."""
    product = create_product(client, sku="ACC-RETURN")
    customer = create_party(client, "Return Customer", "customer")

    post_transaction(client, "purchase", product["id"], 10, 100)
    sale = post_transaction(client, "sale", product["id"], 5, 100, party_id=customer["id"])
    assert Decimal(str(stock(client, product["id"]))) == Decimal("5")

    returned = client.post(
        "/api/movements/sales-returns",
        headers=login_headers(client, "manager"),
        json={
            "original_sale_id": sale["id"],
            "quantity_grams": 2,
            "created_by": "acceptance",
        },
    )
    assert returned.status_code == 201, returned.text
    assert Decimal(str(stock(client, product["id"]))) == Decimal("7")
    assert Decimal(str(party_by_name(client, "Return Customer")["receivable"])) == Decimal("300")


def test_cancel_paid_sale_journey(client):
    """Cancelling a paid sale reverses stock and refunds the money."""
    product = create_product(client, sku="ACC-CANCEL")
    customer = create_party(client, "Cancel Customer", "customer")

    post_transaction(client, "purchase", product["id"], 10, 100)
    sale = post_transaction(
        client, "sale", product["id"], 4, 100,
        party_id=customer["id"], amount_paid=200,
    )
    assert Decimal(str(stock(client, product["id"]))) == Decimal("6")

    # Money already moved: a naive cancel is blocked first.
    blocked = client.post(
        f"/api/transactions/{sale['id']}/cancel",
        headers=login_headers(client, "manager"),
        json={"reason": "customer changed mind"},
    )
    assert blocked.status_code == 409

    allowed = client.post(
        f"/api/transactions/{sale['id']}/cancel",
        headers=login_headers(client, "manager"),
        json={"reason": "customer changed mind", "include_payments": True},
    )
    assert allowed.status_code == 200, allowed.text
    # Stock restored, customer owes nothing (200 paid - 200 refund).
    assert Decimal(str(stock(client, product["id"]))) == Decimal("10")
    assert Decimal(str(party_by_name(client, "Cancel Customer")["receivable"])) == Decimal("0")


def test_oversell_and_overpay_guards(client):
    """The two money/stock guards a shop owner depends on."""
    product = create_product(client, sku="ACC-GUARD")

    post_transaction(client, "purchase", product["id"], 5, 100)
    sale = post_transaction(client, "sale", product["id"], 4, 100, amount_paid=400)

    # Cannot sell stock that does not exist.
    oversell = client.post(
        "/api/sales",
        headers=login_headers(client, "operator"),
        json=transaction_payload(product["id"], weight=2, rate=100),
    )
    assert oversell.status_code == 409

    # Cannot overpay an already-settled transaction.
    overpay = client.post(
        f"/api/transactions/{sale['id']}/payments",
        headers=login_headers(client, "operator"),
        json={"amount": "50", "method": "cash"},
    )
    assert overpay.status_code == 422


def test_pos_double_submit_records_one_sale(client):
    """A double-clicked checkout (same Idempotency-Key) sells once."""
    product = create_product(client, sku="ACC-POS")
    post_transaction(client, "purchase", product["id"], 10, 100)
    payload = transaction_payload(product["id"], weight=1, rate=100)

    headers = {
        **login_headers(client, "operator"),
        "Idempotency-Key": "acceptance-double-click",
    }
    first = client.post("/api/sales", headers=headers, json=payload)
    second = client.post("/api/sales", headers=headers, json=payload)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert Decimal(str(stock(client, product["id"]))) == Decimal("9")


def test_role_boundaries_journey(client):
    """Each role can do exactly its part of the job."""
    product = create_product(client, sku="ACC-ROLES")
    post_transaction(client, "purchase", product["id"], 5, 100)
    sale_payload = transaction_payload(product["id"], weight=1, rate=100)

    viewer = login_headers(client, "viewer")
    operator = login_headers(client, "operator")
    manager = login_headers(client, "manager")
    admin = login_headers(client, "admin")

    # Viewer reads but cannot sell or manage users.
    assert client.get("/api/products", headers=viewer).status_code == 200
    assert client.post("/api/sales", headers=viewer, json=sale_payload).status_code == 403
    assert client.get("/api/users", headers=viewer).status_code == 403

    # Operator sells but cannot manage users.
    assert client.post("/api/sales", headers=operator, json=sale_payload).status_code == 201
    assert client.get("/api/users", headers=operator).status_code == 403

    # Manager runs the shop but user administration stays with admin.
    assert client.get("/api/users", headers=manager).status_code == 403
    assert client.post(
        "/api/users", headers=manager, json={"username": "x", "password": "y", "role": "viewer"}
    ).status_code == 403
    assert client.get("/api/users", headers=admin).status_code == 200


def test_user_lifecycle_journey(client):
    """Admin onboards a cashier; the cashier's identity evolves safely."""
    admin = login_headers(client, "admin")

    created = client.post(
        "/api/users",
        headers=admin,
        json={"username": "cashier_rizwan", "password": "CashierPass1234!", "role": "operator"},
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]

    # The new cashier logs in and works.
    rizwan = client.post(
        "/api/auth/login",
        json={"username": "cashier_rizwan", "password": "CashierPass1234!"},
    )
    assert rizwan.status_code == 200, rizwan.text
    rizwan_headers = {"Authorization": f"Bearer {rizwan.json()['access_token']}"}
    product = create_product(client, sku="ACC-USERFLOW")
    sold = client.post(
        "/api/sales", headers=rizwan_headers, json=transaction_payload(product["id"], 1, 100)
    )
    # Authorization is what matters here; stock may legitimately be empty.
    assert sold.status_code in (201, 409)

    # Rename and password reset; the old password stops working.
    renamed = client.patch(
        f"/api/users/{user_id}/username",
        headers=admin,
        json={"username": "cashier_rizwan2"},
    )
    assert renamed.status_code == 200
    reset = client.patch(
        f"/api/users/{user_id}/password",
        headers=admin,
        json={"password": "NewCashierPass9876!"},
    )
    assert reset.status_code == 200

    assert client.post(
        "/api/auth/login", json={"username": "cashier_rizwan2", "password": "NewCashierPass9876!"}
    ).status_code == 200
    assert client.post(
        "/api/auth/login", json={"username": "cashier_rizwan2", "password": "CashierPass1234!"}
    ).status_code == 401


def test_settings_and_backup_journey(client):
    """Admin personalises the shop, then a backup/restore drill rolls
    later changes back."""
    admin = login_headers(client, "admin")

    saved = client.put(
        "/api/settings",
        headers=admin,
        json={"business_name": "SNJ Gold Lab Acceptance", "currency": "PKR"},
    )
    assert saved.status_code == 200
    settings = client.get("/api/settings", headers=admin).json()
    assert settings["business_name"] == "SNJ Gold Lab Acceptance"

    # Create a product, take a JSON backup, then create another product.
    before = create_product(client, sku="ACC-BAK1")
    backup = client.post("/api/backups/json", headers=admin)
    assert backup.status_code == 201, backup.text
    create_product(client, sku="ACC-BAK2")
    products = client.get("/api/products", headers=admin).json()
    assert any(row["sku"] == "ACC-BAK2" for row in products)

    # Restoring the backup removes the later product; the first survives.
    filename = backup.json()["filename"]
    restored = client.post(
        f"/api/backups/json/{filename}/restore",
        headers=admin,
        json={"confirm": filename},
    )
    assert restored.status_code == 200, restored.text
    products = client.get("/api/products", headers=admin).json()
    assert any(row["sku"] == "ACC-BAK1" for row in products)
    assert not any(row["sku"] == "ACC-BAK2" for row in products)
    assert before["id"] in {row["id"] for row in products}
