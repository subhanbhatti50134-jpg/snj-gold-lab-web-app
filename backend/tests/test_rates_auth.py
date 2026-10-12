import pytest


def test_rates_require_login(client):
    assert client.get("/api/rates").status_code == 401
    assert client.get("/api/rates/1").status_code == 401
    assert client.post("/api/rates", json={}).status_code == 401


@pytest.mark.parametrize("role", ["operator", "viewer"])
def test_lower_roles_cannot_create_rate(client, auth_headers, role):
    response = client.post("/api/rates", json={}, headers=auth_headers(role))
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["admin", "manager"])
def test_manage_roles_pass_the_role_check(client, auth_headers, role):
    # An empty body is invalid, so 422 proves the role check passed.
    response = client.post("/api/rates", json={}, headers=auth_headers(role))
    assert response.status_code == 422


def test_viewer_can_read_rates(client, auth_headers):
    response = client.get("/api/rates", headers=auth_headers("viewer"))
    assert response.status_code == 200, response.text
