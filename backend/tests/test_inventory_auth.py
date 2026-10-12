def test_inventory_requires_login(client):
    assert client.get("/api/inventory").status_code == 401


def test_viewer_can_read_inventory(client, auth_headers):
    response = client.get("/api/inventory", headers=auth_headers("viewer"))
    assert response.status_code == 200, response.text


def test_inventory_location_filter_works(client, auth_headers):
    response = client.get(
        "/api/inventory",
        params={"location": "Main Store"},
        headers=auth_headers("operator"),
    )
    assert response.status_code == 200, response.text
