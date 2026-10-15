from helpers import login_headers
from test_api import create_product, transaction_payload


def create_purchase(client, product_id, weight=5, amount_paid=0):
    payload = transaction_payload(product_id, weight=weight, rate=100)
    payload["amount_paid"] = amount_paid

    response = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_reports_require_login(client):
    for endpoint in (
        "/api/reports/summary",
        "/api/reports/outstanding",
        "/api/reports/party-ledger?party_name=Test%20Customer",
    ):
        response = client.get(endpoint)
        assert response.status_code == 401, (endpoint, response.text)


def test_reports_forbid_anonymous_writes(client):
    # Read endpoints must not accept a bare API key either.
    response = client.get(
        "/api/reports/summary",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 401


def test_summary_reports_purchase_total_and_due(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5, amount_paid=200)

    response = client.get(
        "/api/reports/summary",
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert float(data["purchase"]["total_amount"]) == 500
    assert float(data["purchase"]["amount_paid"]) == 200
    assert float(data["purchase"]["remaining_amount"]) == 300


def test_outstanding_report_lists_unpaid_purchase(client):
    product = create_product(client)
    purchase = create_purchase(
        client, product["id"], weight=5, amount_paid=100
    )

    response = client.get(
        "/api/reports/outstanding",
        params={"kind": "purchase"},
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 200, response.text
    data = response.json()

    matching = [
        item for item in data["items"]
        if item["transaction_id"] == purchase["id"]
    ]
    assert len(matching) == 1
    assert float(matching[0]["remaining_amount"]) == 400


def test_party_ledger_returns_transaction(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"], weight=3)

    response = client.get(
        "/api/reports/party-ledger",
        params={"party_name": "Test Customer"},
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["transaction_count"] == 1
    assert data["transactions"][0]["transaction_id"] == purchase["id"]


def test_summary_rejects_invalid_date_range(client):
    response = client.get(
        "/api/reports/summary",
        params={
            "date_from": "2026-10-12",
            "date_to": "2026-10-01",
        },
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 422


def make_outstanding_sale(client, product_id, **extra):
    response = client.post(
        "/api/sales",
        headers=login_headers(client, "operator"),
        json=transaction_payload(product_id, weight=5, rate=100, amount_paid=100)
        | extra,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_outstanding_includes_party_phone_via_party_id(client):
    party = client.post(
        "/api/parties",
        headers=login_headers(client, "manager"),
        json={"name": "Phone Customer", "phone": "0300-1234567"},
    )
    assert party.status_code == 201, party.text
    product = create_product(client)
    create_purchase(client, product["id"], weight=5, amount_paid=500)
    make_outstanding_sale(
        client, product["id"], party_id=party.json()["id"]
    )

    response = client.get(
        "/api/reports/outstanding",
        params={"kind": "sale"},
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 200, response.text
    pid = party.json()["id"]
    rows = [r for r in response.json()["items"] if r["party_id"] == pid]
    assert rows, "expected an outstanding sale for the party"
    assert rows[0]["party_phone"] == "0300-1234567"


def test_outstanding_resolves_party_phone_by_name(client):
    party = client.post(
        "/api/parties",
        headers=login_headers(client, "manager"),
        json={"name": "Walk-in Credit", "phone": "03119998877"},
    )
    assert party.status_code == 201, party.text
    product = create_product(client)
    create_purchase(client, product["id"], weight=5, amount_paid=500)
    make_outstanding_sale(
        client, product["id"], party_name="Walk-in Credit"
    )

    response = client.get(
        "/api/reports/outstanding",
        params={"kind": "sale", "party_name": "Walk-in Credit"},
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 200, response.text
    rows = response.json()["items"]
    assert rows, "expected an outstanding sale for the walk-in party"
    assert rows[0]["party_id"] is None
    assert rows[0]["party_phone"] == "03119998877"


def test_outstanding_without_party_has_empty_phone(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5, amount_paid=500)
    make_outstanding_sale(
        client, product["id"], party_name="No Party Row"
    )

    response = client.get(
        "/api/reports/outstanding",
        params={"kind": "sale", "party_name": "No Party Row"},
        headers=login_headers(client, "viewer"),
    )

    assert response.status_code == 200, response.text
    rows = response.json()["items"]
    assert rows
    assert rows[0]["party_phone"] == ""
