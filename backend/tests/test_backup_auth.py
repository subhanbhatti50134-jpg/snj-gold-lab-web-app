from helpers import login_headers


def test_backup_listing_requires_admin(client, auth_headers):
    assert client.get("/api/backups").status_code == 401

    for role in ("viewer", "operator", "manager"):
        response = client.get("/api/backups", headers=auth_headers(role))
        assert response.status_code == 403, role


def test_backup_create_requires_admin(client, auth_headers):
    response = client.post("/api/backups", headers=auth_headers("manager"))
    assert response.status_code == 403


def test_restore_rejects_wrong_confirmation(client, auth_headers):
    headers = auth_headers("admin")
    response = client.post(
        "/api/backups/any-file.dump/restore",
        headers=headers,
        json={"confirm": "different-name.dump"},
    )
    assert response.status_code == 422


def test_restore_rejects_path_traversal(client, auth_headers):
    headers = auth_headers("admin")
    response = client.post(
        "/api/backups/..%2F..%2Fetc%2Fpasswd.dump/restore",
        headers=headers,
        json={"confirm": "../../etc/passwd.dump"},
    )
    assert response.status_code in (404, 422)


def test_restore_missing_file_is_404(client, auth_headers):
    headers = auth_headers("admin")
    response = client.post(
        "/api/backups/no-such-backup.dump/restore",
        headers=headers,
        json={"confirm": "no-such-backup.dump"},
    )
    assert response.status_code == 404


def test_viewer_cannot_restore(client, auth_headers):
    response = client.post(
        "/api/backups/x.dump/restore",
        headers=auth_headers("viewer"),
        json={"confirm": "x.dump"},
    )
    assert response.status_code == 403


def test_backup_listing_returns_list_for_admin(client):
    response = client.get(
        "/api/backups", headers=login_headers(client, "admin")
    )
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)
