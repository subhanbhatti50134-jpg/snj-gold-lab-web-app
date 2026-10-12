import pytest

PRODUCT = {
    "sku": "AUTH-GOLD-001",
    "name": "Auth Test Gold",
    "category": "loose_metal",
    "metal": "gold",
    "purity": 100,
}


def test_products_require_login(client):
    assert client.get("/api/products").status_code == 401
    assert client.get("/api/products/1").status_code == 401
    assert client.post("/api/products", json=PRODUCT).status_code == 401


@pytest.mark.parametrize("role", ["admin", "manager"])
def test_manage_roles_can_create_product(client, auth_headers, role):
    response = client.post(
        "/api/products", json=PRODUCT, headers=auth_headers(role)
    )
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("role", ["operator", "viewer"])
def test_lower_roles_cannot_create_product(client, auth_headers, role):
    response = client.post(
        "/api/products", json=PRODUCT, headers=auth_headers(role)
    )
    assert response.status_code == 403


def test_viewer_can_read_products(client, auth_headers):
    created = client.post(
        "/api/products", json=PRODUCT, headers=auth_headers("manager")
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]

    viewer = auth_headers("viewer")
    assert client.get("/api/products", headers=viewer).status_code == 200
    assert (
        client.get(f"/api/products/{product_id}", headers=viewer).status_code
        == 200
    )
