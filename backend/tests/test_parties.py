from decimal import Decimal

from helpers import login_headers
from test_api import create_product, transaction_payload


def create_party(client, name="Ashraf Jewellers", kind="customer"):
    response = client.post(
        "/api/parties",
        headers=login_headers(client, "manager"),
        json={"name": name, "kind": kind, "phone": "0300-1234567"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_transaction(client, kind, product_id, party_id, weight=5, amount_paid=0):
    payload = transaction_payload(
        product_id, weight=weight, rate=100, amount_paid=amount_paid
    )
    payload["party_id"] = party_id
    payload.pop("party_name")

    response = client.post(
        f"/api/{kind}s",
        headers=login_headers(client, "operator"),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_party_requires_login(client):
    assert client.get("/api/parties").status_code == 401
    assert client.post("/api/parties", json={}).status_code == 401


def test_viewer_cannot_create_parties(client, auth_headers):
    headers = auth_headers("viewer")
    response = client.post(
        "/api/parties",
        headers=headers,
        json={"name": "Viewer Party"},
    )
    assert response.status_code == 403


def test_party_crud_and_duplicate_name(client):
    party = create_party(client)

    assert party["name"] == "Ashraf Jewellers"
    assert party["kind"] == "customer"
    assert Decimal(str(party["receivable"])) == Decimal("0")

    duplicate = client.post(
        "/api/parties",
        headers=login_headers(client, "manager"),
        json={"name": "Ashraf Jewellers"},
    )
    assert duplicate.status_code == 409

    updated = client.patch(
        f"/api/parties/{party['id']}",
        headers=login_headers(client, "manager"),
        json={"phone": "0333-9999999", "kind": "both"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["phone"] == "0333-9999999"
    assert updated.json()["kind"] == "both"

    listing = client.get(
        "/api/parties",
        headers=login_headers(client, "viewer"),
    )
    assert listing.status_code == 200
    assert any(row["id"] == party["id"] for row in listing.json())


def test_party_balances_from_sales_and_purchases(client):
    product = create_product(client)
    customer = create_party(client, name="Customer One", kind="customer")
    supplier = create_party(client, name="Supplier One", kind="supplier")

    # Purchase of 10g at 100/g fully paid -> no payable, but stock in.
    create_transaction(
        client, "purchase", product["id"], supplier["id"],
        weight=10, amount_paid=1000,
    )
    # Sale of 5g at 100/g with 200 paid -> 300 receivable.
    create_transaction(
        client, "sale", product["id"], customer["id"],
        weight=5, amount_paid=200,
    )

    listing = client.get(
        "/api/parties",
        headers=login_headers(client, "viewer"),
    ).json()
    by_name = {row["name"]: row for row in listing}

    assert Decimal(str(by_name["Customer One"]["receivable"])) == Decimal("300")
    assert Decimal(str(by_name["Customer One"]["payable"])) == Decimal("0")
    assert Decimal(str(by_name["Supplier One"]["payable"])) == Decimal("0")


def test_purchase_outstanding_shows_payable(client):
    product = create_product(client)
    supplier = create_party(client, name="Supplier Due", kind="supplier")

    create_transaction(
        client, "purchase", product["id"], supplier["id"],
        weight=10, amount_paid=0,
    )

    listing = client.get(
        "/api/parties",
        params={"kind": "supplier"},
        headers=login_headers(client, "viewer"),
    ).json()
    by_name = {row["name"]: row for row in listing}

    assert Decimal(str(by_name["Supplier Due"]["payable"])) == Decimal("1000")
    assert Decimal(str(by_name["Supplier Due"]["net"])) == Decimal("-1000")


def test_sales_return_reduces_receivable(client):
    """A return of goods lowers what the customer owes."""
    product = create_product(client)
    customer = create_party(client, name="Return Customer", kind="customer")
    supplier = create_party(client, name="Return Supplier", kind="supplier")

    # Stock in: 10g at 100/g = 1000.
    create_transaction(
        client, "purchase", product["id"], supplier["id"],
        weight=10, amount_paid=0,
    )
    # Customer buys 5g for 500, pays nothing yet.
    sale = create_transaction(
        client, "sale", product["id"], customer["id"],
        weight=5, amount_paid=0,
    )

    # Receivable before the return is the full 500.
    before = {
        row["name"]: row
        for row in client.get(
            "/api/parties", headers=login_headers(client, "viewer")
        ).json()
    }
    assert Decimal(str(before["Return Customer"]["receivable"])) == Decimal("500")

    # Customer returns 2g (value 200 at the original rate).
    returned = client.post(
        "/api/movements/sales-returns",
        headers=login_headers(client, "manager"),
        json={
            "original_sale_id": sale["id"],
            "quantity_grams": 2,
            "created_by": "Pytest",
        },
    )
    assert returned.status_code == 201, returned.text

    after = {
        row["name"]: row
        for row in client.get(
            "/api/parties", headers=login_headers(client, "viewer")
        ).json()
    }
    # 500 owed - 200 returned = 300 still receivable.
    assert (
        Decimal(str(after["Return Customer"]["receivable"]))
        == Decimal("300")
    )


def test_cancelling_return_restores_receivable(client):
    """Reversing a return puts the value back on the customer's ledger."""
    product = create_product(client)
    customer = create_party(client, name="Cancel Customer", kind="customer")
    supplier = create_party(client, name="Cancel Supplier", kind="supplier")

    create_transaction(
        client, "purchase", product["id"], supplier["id"],
        weight=10, amount_paid=0,
    )
    sale = create_transaction(
        client, "sale", product["id"], customer["id"],
        weight=5, amount_paid=0,
    )

    returned = client.post(
        "/api/movements/sales-returns",
        headers=login_headers(client, "manager"),
        json={
            "original_sale_id": sale["id"],
            "quantity_grams": 2,
            "created_by": "Pytest",
        },
    )
    assert returned.status_code == 201, returned.text

    cancelled = client.post(
        f"/api/transactions/{returned.json()['id']}/cancel",
        headers=login_headers(client, "manager"),
        json={"reason": "Restock test"},
    )
    assert cancelled.status_code == 200, cancelled.text

    after = {
        row["name"]: row
        for row in client.get(
            "/api/parties", headers=login_headers(client, "viewer")
        ).json()
    }
    # Return no longer counts, so the customer owes the full 500 again.
    assert (
        Decimal(str(after["Cancel Customer"]["receivable"]))
        == Decimal("500")
    )


def test_transaction_uses_party_name_from_party_record(client):
    product = create_product(client)
    party = create_party(client, name="Canonical Name")

    payload = transaction_payload(product["id"], weight=5, rate=100)
    payload["party_id"] = party["id"]
    payload["party_name"] = "Ignored Client Text"

    response = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=payload,
    )

    assert response.status_code == 201, response.text
    assert response.json()["party_name"] == "Canonical Name"
    assert response.json()["party_id"] == party["id"]


def test_unknown_party_is_rejected(client):
    product = create_product(client)
    payload = transaction_payload(product["id"], weight=5)
    payload["party_id"] = 99999

    response = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=payload,
    )
    assert response.status_code == 404
