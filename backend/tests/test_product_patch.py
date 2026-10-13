from helpers import login_headers
from test_api import create_product


def patch_product(client, product_id, changes, role="manager"):
    return client.patch(
        f"/api/products/{product_id}",
        headers=login_headers(client, role),
        json=changes,
    )


def test_product_update_changes_fields(client):
    product = create_product(client)

    response = patch_product(
        client,
        product["id"],
        {"name": "Updated Gold Bar", "purity": 99.5, "active": False},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "Updated Gold Bar"
    assert float(data["purity"]) == 99.5
    assert data["active"] is False

    inactive_list = client.get(
        "/api/products",
        params={"include_inactive": "true"},
        headers=login_headers(client, "viewer"),
    ).json()
    assert any(row["id"] == product["id"] for row in inactive_list)

    active_list = client.get(
        "/api/products",
        headers=login_headers(client, "viewer"),
    ).json()
    assert all(row["id"] != product["id"] for row in active_list)


def test_duplicate_sku_on_update_is_rejected(client):
    create_product(client, sku="GOLD-001")
    other = create_product(client, sku="GOLD-002")

    response = patch_product(client, other["id"], {"sku": "GOLD-001"})
    assert response.status_code == 409


def test_empty_patch_is_rejected(client):
    product = create_product(client)
    response = patch_product(client, product["id"], {})
    assert response.status_code == 422


def test_patch_unknown_product_is_404(client):
    response = patch_product(client, 99999, {"name": "Ghost"})
    assert response.status_code == 404


def test_operator_cannot_patch_products(client, auth_headers):
    product = create_product(client)
    response = client.patch(
        f"/api/products/{product['id']}",
        headers=auth_headers("operator"),
        json={"name": "Nope"},
    )
    assert response.status_code == 403


def test_patch_is_audited(client):
    product = create_product(client)
    assert patch_product(client, product["id"], {"name": "Renamed"}).status_code == 200

    logs = client.get(
        "/api/audit",
        params={"action": "product.update"},
        headers=login_headers(client, "admin"),
    ).json()
    assert logs
    assert "name" in logs[0]["detail"]
