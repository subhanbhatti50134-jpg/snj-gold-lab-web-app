from decimal import Decimal

from helpers import login_headers
from test_api import create_product, transaction_payload
from test_reversals import create_purchase, create_sale, stock_at


def purge_tx(client, transaction_id, headers=None):
    return client.delete(
        f"/api/transactions/{transaction_id}",
        headers=headers or login_headers(client, "manager"),
    )


def test_purge_sale_restores_stock_and_removes_row(client):
    product = create_product(client)
    create_purchase(client, product["id"], 10)
    sale = create_sale(client, product["id"], 4)
    assert stock_at(client, product["id"]) == Decimal("6")

    response = purge_tx(client, sale["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deleted"] is True
    assert sale["reference"] in body["detail"]

    # Row is gone, stock is back to the post-purchase balance.
    assert (
        client.get(
            f"/api/transactions/{sale['id']}",
            headers=login_headers(client, "viewer"),
        ).status_code
        == 404
    )
    assert stock_at(client, product["id"]) == Decimal("10")

    audit = client.get(
        "/api/audit",
        params={"action": "transaction.delete"},
        headers=login_headers(client, "admin"),
    ).json()
    assert audit, "purge must leave an audit trail"


def test_purge_sale_with_active_return_is_blocked(client):
    product = create_product(client)
    create_purchase(client, product["id"], 10)
    sale = create_sale(client, product["id"], 4)
    returned = client.post(
        "/api/movements/sales-returns",
        headers=login_headers(client, "manager"),
        json={
            "original_sale_id": sale["id"],
            "quantity_grams": 1,
        },
    )
    assert returned.status_code == 201, returned.text

    blocked = purge_tx(client, sale["id"])
    assert blocked.status_code == 409
    assert "returns" in blocked.json()["detail"]

    # Cancelling the return unblocks the purge.
    cancel_return = client.post(
        f"/api/transactions/{returned.json()['id']}/cancel",
        headers=login_headers(client, "manager"),
        json={"reason": "keep the sale"},
    )
    assert cancel_return.status_code == 200, cancel_return.text
    assert purge_tx(client, sale["id"]).status_code == 200


def test_purge_purchase_guarding_negative_stock(client):
    product = create_product(client)
    first = create_purchase(client, product["id"], 10)
    create_purchase(client, product["id"], 4)
    create_sale(client, product["id"], 12)
    assert stock_at(client, product["id"]) == Decimal("2")

    # Removing the 10g purchase would take stock to -8g.
    blocked = purge_tx(client, first["id"])
    assert blocked.status_code == 409
    assert "negative stock" in blocked.json()["detail"]


def test_purge_cancelled_transaction(client):
    product = create_product(client)
    purchase = create_purchase(client, product["id"], 10, amount_paid=100)
    cancel = client.post(
        f"/api/transactions/{purchase['id']}/cancel",
        headers=login_headers(client, "manager"),
        json={"reason": "mistake", "include_payments": True},
    )
    assert cancel.status_code == 200, cancel.text
    assert stock_at(client, product["id"]) == Decimal("0")

    response = purge_tx(client, purchase["id"])
    assert response.status_code == 200, response.text
    assert (
        client.get(
            f"/api/transactions/{purchase['id']}",
            headers=login_headers(client, "viewer"),
        ).status_code
        == 404
    )
    assert stock_at(client, product["id"]) == Decimal("0")


def test_purge_requires_manager(client):
    product = create_product(client)
    create_purchase(client, product["id"], 1)
    sale = create_sale(client, product["id"], 1)
    response = purge_tx(
        client, sale["id"], headers=login_headers(client, "operator")
    )
    assert response.status_code == 403


def test_purge_missing_transaction(client):
    assert purge_tx(client, 99999).status_code == 404


def test_purge_unused_product(client):
    product = create_product(client, sku="DELETE-ME")
    response = client.delete(
        f"/api/products/{product['id']}",
        headers=login_headers(client, "manager"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["deleted"] is True
    assert (
        client.get(
            f"/api/products/{product['id']}",
            headers=login_headers(client, "viewer"),
        ).status_code
        == 404
    )


def test_purge_used_product_is_blocked(client):
    product = create_product(client)
    create_purchase(client, product["id"], 2)
    response = client.delete(
        f"/api/products/{product['id']}",
        headers=login_headers(client, "manager"),
    )
    assert response.status_code == 409
    assert "Deactivate" in response.json()["detail"]


def test_purge_product_requires_manager(client):
    product = create_product(client, sku="VIEWER-NO")
    response = client.delete(
        f"/api/products/{product['id']}",
        headers=login_headers(client, "operator"),
    )
    assert response.status_code == 403


def test_purge_unused_party(client):
    created = client.post(
        "/api/parties",
        headers=login_headers(client, "manager"),
        json={
            "name": "Delete Me Traders",
            "kind": "customer",
            "phone": "0300-0000000",
        },
    )
    assert created.status_code == 201, created.text
    party_id = created.json()["id"]

    response = client.delete(
        f"/api/parties/{party_id}",
        headers=login_headers(client, "manager"),
    )
    assert response.status_code == 200, response.text
    listing = client.get(
        "/api/parties",
        params={"include_inactive": "true", "search": "Delete Me"},
        headers=login_headers(client, "viewer"),
    ).json()
    assert listing == []


def test_purge_used_party_is_blocked(client):
    created = client.post(
        "/api/parties",
        headers=login_headers(client, "manager"),
        json={
            "name": "Keep Me Traders",
            "kind": "customer",
            "phone": "0300-1111111",
        },
    )
    party_id = created.json()["id"]
    product = create_product(client)
    create_purchase(client, product["id"], 5)
    sale = client.post(
        "/api/sales",
        headers=login_headers(client, "operator"),
        json={
            **transaction_payload(product["id"], 1),
            "party_id": party_id,
        },
    )
    assert sale.status_code == 201, sale.text

    response = client.delete(
        f"/api/parties/{party_id}",
        headers=login_headers(client, "manager"),
    )
    assert response.status_code == 409
    assert "Deactivate" in response.json()["detail"]


def test_purge_missing_party(client):
    response = client.delete(
        "/api/parties/99999", headers=login_headers(client, "manager")
    )
    assert response.status_code == 404
