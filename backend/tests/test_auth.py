

from app.core.auth import hash_password
from app.models.user import User


def create_user(db, username="testuser", password="CorrectPass123", active=True):
    user = User(
        username=username,
        password_hash=hash_password(password),
        role="operator",
        active=active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_login_returns_access_token(client, db):
    create_user(db)

    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "CorrectPass123"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800
    assert data["access_token"]


def test_login_rejects_wrong_password(client, db):
    create_user(db)

    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "WrongPassword"},
    )

    assert response.status_code == 401


def test_me_returns_authenticated_user(client, db):
    user = create_user(db)

    login = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "CorrectPass123"},
    )
    assert login.status_code == 200, login.text

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": user.id,
        "username": "testuser",
        "role": "operator",
        "active": True,
    }


def test_me_rejects_invalid_token(client):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_inactive_user_cannot_login(client, db):
    create_user(db, active=False)

    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "CorrectPass123"},
    )

    assert response.status_code == 401
