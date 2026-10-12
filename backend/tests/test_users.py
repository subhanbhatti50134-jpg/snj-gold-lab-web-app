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


def test_user_management_requires_api_key(client, db):
    headers = admin_headers(client, db)
    headers.pop("X-API-Key")

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
