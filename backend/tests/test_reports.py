from test_api import API_HEADERS, create_product, transaction_payload


def create_purchase(client, product_id, weight=5, amount_paid=0):
    payload = transaction_payload(product_id, weight=weight, rate=100)
    payload["amount_paid"] = amount_paid

    response = client.post(
        "/api/purchases",
        headers=API_HEADERS,
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_reports_require_api_key(client):
    for endpoint in (
        "/api/reports/summary",
        "/api/reports/outstanding",
        "/api/reports/party-ledger?party_name=Test%20Customer",
    ):
        response = client.get(endpoint)
        assert response.status_code == 401, (endpoint, response.text)


def test_summary_reports_purchase_total_and_due(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5, amount_paid=200)

    response = client.get(
        "/api/reports/summary",
        headers=API_HEADERS,
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
        headers=API_HEADERS,
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
        headers=API_HEADERS,
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
        headers=API_HEADERS,
    )

    assert response.status_code == 422
