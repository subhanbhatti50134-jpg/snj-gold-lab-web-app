from helpers import login_headers
from test_api import create_product, transaction_payload
from test_reports import create_purchase


def export_get(client, path, role="viewer"):
    return client.get(path, headers=login_headers(client, role))


def test_export_requires_login(client):
    for path in (
        "/api/export/transactions.csv",
        "/api/export/outstanding.csv",
        "/api/export/parties.csv",
        "/api/export/party-ledger.csv?party_name=X",
    ):
        assert client.get(path).status_code == 401, path


def test_transactions_csv_downloads_with_bom(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"], weight=5)

    response = export_get(client, "/api/export/transactions.csv?kind=purchase")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert ".csv" in response.headers["content-disposition"]

    text = response.text
    assert text.startswith("\ufeff")  # UTF-8 BOM for Excel
    assert "reference,kind,status,date" in text
    assert purchase["reference"] in text
    assert "sale" not in text.splitlines()[1]  # kind filter applied


def test_transactions_csv_respects_kind_filter(client):
    product = create_product(client)
    create_purchase(client, product["id"], weight=5)

    response = export_get(client, "/api/export/transactions.csv?kind=sale")

    assert response.status_code == 200, response.text
    header, *rows = response.text.lstrip("\ufeff").splitlines()
    assert rows == [] or "purchase" not in "".join(rows)


def test_outstanding_csv_includes_party_phone(client):
    party = client.post(
        "/api/parties",
        headers=login_headers(client, "manager"),
        json={"name": "CSV Customer", "phone": "03451112233"},
    )
    assert party.status_code == 201, party.text
    product = create_product(client)
    create_purchase(client, product["id"], weight=5, amount_paid=500)
    sale = client.post(
        "/api/sales",
        headers=login_headers(client, "operator"),
        json=transaction_payload(
            product["id"], weight=2, rate=100, amount_paid=50
        )
        | {"party_id": party.json()["id"]},
    )
    assert sale.status_code == 201, sale.text

    response = export_get(client, "/api/export/outstanding.csv?kind=sale")

    assert response.status_code == 200, response.text
    text = response.text
    assert "03451112233" in text
    assert "reference,kind,party,phone" in text.lstrip("\ufeff")


def test_parties_csv_lists_all_roles_visible_rows(client):
    created = client.post(
        "/api/parties",
        headers=login_headers(client, "manager"),
        json={"name": "CSV Supplier", "phone": "03000000001", "kind": "supplier"},
    )
    assert created.status_code == 201, created.text

    response = export_get(client, "/api/export/parties.csv")

    assert response.status_code == 200, response.text
    text = response.text.lstrip("\ufeff")
    assert "CSV Supplier" in text
    assert "receivable,payable,net" in text.splitlines()[0]


def test_party_ledger_csv_requires_party_name(client):
    missing = export_get(client, "/api/export/party-ledger.csv")
    assert missing.status_code == 422

    product = create_product(client)
    create_purchase(client, product["id"], weight=3)
    response = export_get(
        client, "/api/export/party-ledger.csv?party_name=Test%20Customer"
    )
    assert response.status_code == 200, response.text
    text = response.text.lstrip("\ufeff")
    assert "date,reference,kind,party,quantity_grams" in text.splitlines()[0]
    assert "Test Customer" in text


def test_csv_neutralises_formula_injection(client):
    client.post(
        "/api/parties",
        headers=login_headers(client, "manager"),
        json={"name": "=EVIL_CMD()", "phone": "03001231234"},
    )

    response = export_get(client, "/api/export/parties.csv")

    assert response.status_code == 200, response.text
    assert "'=EVIL_CMD()" in response.text
    assert ",=EVIL_CMD()" not in response.text
