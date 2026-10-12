import pytest

ENDPOINTS = [
    "/api/movements/sales-returns",
    "/api/movements/adjustments",
]


@pytest.mark.parametrize("url", ENDPOINTS)
def test_requires_login(client, url):
    assert client.post(url, json={}).status_code == 401


@pytest.mark.parametrize("role", ["operator", "viewer"])
@pytest.mark.parametrize("url", ENDPOINTS)
def test_lower_roles_are_forbidden(client, auth_headers, url, role):
    response = client.post(url, json={}, headers=auth_headers(role))
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["manager", "admin"])
@pytest.mark.parametrize("url", ENDPOINTS)
def test_manage_roles_pass_the_role_check(client, auth_headers, url, role):
    # Empty body is invalid, so 422 proves the role check passed.
    response = client.post(url, json={}, headers=auth_headers(role))
    assert response.status_code == 422
