import pytest

ENDPOINTS = ["/api/purchases", "/api/sales"]


@pytest.mark.parametrize("url", ENDPOINTS)
def test_requires_login(client, url):
    assert client.get(url).status_code == 401
    assert client.post(url, json={}).status_code == 401


@pytest.mark.parametrize("url", ENDPOINTS)
def test_viewer_cannot_create_or_list(client, auth_headers, url):
    headers = auth_headers("viewer")
    assert client.post(url, json={}, headers=headers).status_code == 403
    assert client.get(url, headers=headers).status_code == 403


@pytest.mark.parametrize("role", ["operator", "manager", "admin"])
@pytest.mark.parametrize("url", ENDPOINTS)
def test_operate_roles_pass_role_check(client, auth_headers, url, role):
    headers = auth_headers(role)
    # Empty body is invalid, so 422 proves the role check passed.
    assert client.post(url, json={}, headers=headers).status_code == 422
    assert client.get(url, headers=headers).status_code == 200
