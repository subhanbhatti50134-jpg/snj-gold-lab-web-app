from decimal import Decimal

from helpers import login_headers
from test_api import create_product, transaction_payload
from test_reports import create_purchase


def make_sale(client, payload):
    return client.post(
        "/api/sales",
        headers=login_headers(client, "operator"),
        json=payload,
    )


def test_sale_with_per_gram_making(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)

    payload = transaction_payload(product["id"], weight=2, rate=100)
    payload["making_charge_type"] = "per_gram"
    payload["making_charge_value"] = 15

    response = make_sale(client, payload)
    assert response.status_code == 201, response.text
    row = response.json()
    # metal 2*100 = 200, ujra 2*15 = 30
    assert Decimal(row["making_amount"]) == Decimal("30")
    assert Decimal(row["total_amount"]) == Decimal("230")
    assert row["making_charge_type"] == "per_gram"
    assert Decimal(row["making_charge_value"]) == Decimal("15")


def test_sale_with_percent_making(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)

    payload = transaction_payload(product["id"], weight=2, rate=100)
    payload["making_charge_type"] = "percent"
    payload["making_charge_value"] = 10

    response = make_sale(client, payload)
    assert response.status_code == 201, response.text
    row = response.json()
    # 10% of metal value 200 = 20
    assert Decimal(row["making_amount"]) == Decimal("20")
    assert Decimal(row["total_amount"]) == Decimal("220")


def test_sale_with_fixed_making(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)

    payload = transaction_payload(product["id"], weight=2, rate=100)
    payload["making_charge_type"] = "fixed"
    payload["making_charge_value"] = 500

    response = make_sale(client, payload)
    assert response.status_code == 201, response.text
    row = response.json()
    assert Decimal(row["making_amount"]) == Decimal("500")
    assert Decimal(row["total_amount"]) == Decimal("700")


def test_making_charge_with_charges_stacks(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)

    payload = transaction_payload(product["id"], weight=2, rate=100)
    payload["charges"] = 25
    payload["making_charge_type"] = "fixed"
    payload["making_charge_value"] = 50

    response = make_sale(client, payload)
    assert response.status_code == 201, response.text
    row = response.json()
    assert Decimal(row["total_amount"]) == Decimal("275")


def test_purchase_rejects_making_charge(client):
    product = create_product(client)
    payload = transaction_payload(product["id"], weight=5, rate=100)
    payload["making_charge_type"] = "per_gram"
    payload["making_charge_value"] = 10

    response = client.post(
        "/api/purchases",
        headers=login_headers(client, "operator"),
        json=payload,
    )
    assert response.status_code == 422, response.text
    assert "sales only" in response.json()["detail"]


def test_making_type_requires_positive_value(client):
    product = create_product(client)
    payload = transaction_payload(product["id"], weight=1, rate=100)
    payload["making_charge_type"] = "per_gram"
    payload["making_charge_value"] = 0

    response = make_sale(client, payload)
    assert response.status_code == 422, response.text


def test_making_value_requires_type(client):
    product = create_product(client)
    payload = transaction_payload(product["id"], weight=1, rate=100)
    payload["making_charge_type"] = ""
    payload["making_charge_value"] = 50

    response = make_sale(client, payload)
    assert response.status_code == 422, response.text


def test_partial_return_refunds_proportional_making(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=10)

    payload = transaction_payload(product["id"], weight=4, rate=100)
    payload["amount_paid"] = 500
    payload["making_charge_type"] = "fixed"
    payload["making_charge_value"] = 100
    sale = make_sale(client, payload)
    assert sale.status_code == 201, sale.text
    assert Decimal(sale.json()["total_amount"]) == Decimal("500")

    response = client.post(
        "/api/movements/sales-returns",
        headers=login_headers(client, "manager"),
        json={"original_sale_id": sale.json()["id"], "quantity_grams": 2},
    )
    assert response.status_code == 201, response.text
    row = response.json()
    # Half the weight returns, so half the flat ujra comes back.
    assert Decimal(row["making_amount"]) == Decimal("50")
    assert Decimal(row["total_amount"]) == Decimal("250")


def test_receipt_detail_exposes_making(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)

    payload = transaction_payload(product["id"], weight=1, rate=100)
    payload["making_charge_type"] = "fixed"
    payload["making_charge_value"] = 40
    sale = make_sale(client, payload)
    assert sale.status_code == 201, sale.text

    response = client.get(
        f"/api/transactions/{sale.json()['id']}",
        headers=login_headers(client, "viewer"),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["making_charge_type"] == "fixed"
    assert Decimal(data["making_amount"]) == Decimal("40")
    assert Decimal(data["total_amount"]) == Decimal("140")


def test_batch_sale_carries_making_charge(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)

    item = transaction_payload(product["id"], weight=1, rate=100)
    item["making_charge_type"] = "per_gram"
    item["making_charge_value"] = 20
    item["amount_paid"] = 120

    response = client.post(
        "/api/sales/batch",
        headers=login_headers(client, "operator"),
        json={"items": [item]},
    )
    assert response.status_code == 201, response.text

    detail = client.get(
        f"/api/transactions/{response.json()[0]['id']}",
        headers=login_headers(client, "viewer"),
    )
    assert Decimal(detail.json()["making_amount"]) == Decimal("20")
    assert Decimal(detail.json()["total_amount"]) == Decimal("120")


def test_transactions_csv_includes_making_columns(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)
    payload = transaction_payload(product["id"], weight=1, rate=100)
    payload["making_charge_type"] = "fixed"
    payload["making_charge_value"] = 30
    make_sale(client, payload)

    response = client.get(
        "/api/export/transactions.csv?kind=sale",
        headers=login_headers(client, "viewer"),
    )
    assert response.status_code == 200, response.text
    header = response.text.lstrip("\ufeff").splitlines()[0]
    assert "making_type,making_value,making_amount" in header
    assert ",fixed,30.0000,30.00," in response.text
