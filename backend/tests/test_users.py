from app.core.auth import hash_password
from app.models.user import User


def create_test_user(db, username, role="operator"):
    user = User(
        username=username,
        password_hash=hash_password("TestPassword123!"),
        role=role,
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def admin_headers(client, db):
    create_test_user(db, "testadmin", role="admin")

    response = client.post(
        "/api/auth/login",
        json={
            "username": "testadmin",
            "password": "TestPassword123!",
        },
    )
    assert response.status_code == 200, response.text

    return {
        "X-API-Key": "test-api-key",
        "Authorization": f"Bearer {response.json()['access_token']}",
    }


def test_user_creation_requires_admin(client, db):
    create_test_user(db, "testoperator", role="operator")

    login = client.post(
        "/api/auth/login",
        json={
            "username": "testoperator",
            "password": "TestPassword123!",
        },
    )
    assert login.status_code == 200

    headers = {
        "X-API-Key": "test-api-key",
        "Authorization": f"Bearer {login.json()['access_token']}",
    }

    response = client.post(
        "/api/users",
        headers=headers,
        json={
            "username": "newoperator",
            "password": "AnotherPassword123!",
            "role": "operator",
        },
    )
    assert response.status_code == 403


def test_admin_can_create_user(client, db):
    headers = admin_headers(client, db)

    response = client.post(
        "/api/users",
        headers=headers,
        json={
            "username": "newoperator",
            "password": "AnotherPassword123!",
            "role": "operator",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["username"] == "newoperator"
    assert response.json()["role"] == "operator"
    assert response.json()["active"] is True
    assert "password_hash" not in response.json()


def test_user_management_requires_login(client, db):
    headers = admin_headers(client, db)
    headers.pop("X-API-Key")
    headers.pop("Authorization")

    response = client.get("/api/users", headers=headers)

    assert response.status_code == 401


def test_admin_can_list_users(client, db):
    headers = admin_headers(client, db)
    create_test_user(db, "regularuser")

    response = client.get("/api/users", headers=headers)

    assert response.status_code == 200, response.text
    usernames = [user["username"] for user in response.json()]
    assert "testadmin" in usernames
    assert "regularuser" in usernames


def test_admin_can_reset_any_password(client, db):
    headers = admin_headers(client, db)
    target = create_test_user(db, "resettarget")

    response = client.patch(
        f"/api/users/{target.id}/password",
        headers=headers,
        json={"password": "BrandNewPass123!"},
    )
    assert response.status_code == 200, response.text

    # The old password must no longer work; the new one must.
    old_login = client.post(
        "/api/auth/login",
        json={"username": "resettarget", "password": "TestPassword123!"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        json={"username": "resettarget", "password": "BrandNewPass123!"},
    )
    assert new_login.status_code == 200, new_login.text


def test_password_reset_rejects_short_password(client, db):
    headers = admin_headers(client, db)
    target = create_test_user(db, "shortpw")

    response = client.patch(
        f"/api/users/{target.id}/password",
        headers=headers,
        json={"password": "short"},
    )
    assert response.status_code == 422


def test_password_change_requires_admin(client, db):
    headers = admin_headers(client, db)
    operator = create_test_user(db, "justoperator", role="operator")

    login = client.post(
        "/api/auth/login",
        json={"username": "justoperator", "password": "TestPassword123!"},
    )
    assert login.status_code == 200

    response = client.patch(
        f"/api/users/{operator.id}/password",
        headers={
            "X-API-Key": "test-api-key",
            "Authorization": f"Bearer {login.json()['access_token']}",
        },
        json={"password": "AnotherNewPass123!"},
    )
    assert response.status_code == 403


def test_admin_can_rename_any_user(client, db):
    headers = admin_headers(client, db)
    target = create_test_user(db, "oldname")

    response = client.patch(
        f"/api/users/{target.id}/username",
        headers=headers,
        json={"username": "newname"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["username"] == "newname"

    login = client.post(
        "/api/auth/login",
        json={"username": "newname", "password": "TestPassword123!"},
    )
    assert login.status_code == 200, login.text


def test_rename_rejects_duplicate_username(client, db):
    headers = admin_headers(client, db)
    create_test_user(db, "takenname")
    target = create_test_user(db, "renameme")

    response = client.patch(
        f"/api/users/{target.id}/username",
        headers=headers,
        json={"username": "takenname"},
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_admin_can_rename_self_and_session_survives(client, db):
    """JWTs carry the user id, so renaming the logged-in admin must not
    break their existing session."""
    headers = admin_headers(client, db)

    # Find the admin's id.
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    admin_id = me.json()["id"]

    response = client.patch(
        f"/api/users/{admin_id}/username",
        headers=headers,
        json={"username": "renamedadmin"},
    )
    assert response.status_code == 200, response.text

    # The same token must still work after the rename.
    me_after = client.get("/api/auth/me", headers=headers)
    assert me_after.status_code == 200
    assert me_after.json()["username"] == "renamedadmin"


def test_rename_requires_admin(client, db):
    headers = admin_headers(client, db)
    operator = create_test_user(db, "plainoperator", role="operator")

    login = client.post(
        "/api/auth/login",
        json={"username": "plainoperator", "password": "TestPassword123!"},
    )
    assert login.status_code == 200

    response = client.patch(
        f"/api/users/{operator.id}/username",
        headers={
            "X-API-Key": "test-api-key",
            "Authorization": f"Bearer {login.json()['access_token']}",
        },
        json={"username": "sneakyrename"},
    )
    assert response.status_code == 403
