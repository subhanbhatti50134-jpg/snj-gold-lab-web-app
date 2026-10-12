import pytest

URL = "/api/transactions/1/payments"


def test_requires_login(client):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={}).status_code == 401


def test_viewer_is_forbidden(client, auth_headers):
    headers = auth_headers("viewer")
    assert client.get(URL, headers=headers).status_code == 403
    assert client.post(URL, json={}, headers=headers).status_code == 403


@pytest.mark.parametrize("role", ["operator", "manager", "admin"])
def test_operate_roles_pass_role_check(client, auth_headers, role):
    headers = auth_headers(role)
    # Empty body is invalid, so 422 proves the role check passed.
    assert client.post(URL, json={}, headers=headers).status_code == 422
    assert client.get(URL, headers=headers).status_code not in (401, 403)
