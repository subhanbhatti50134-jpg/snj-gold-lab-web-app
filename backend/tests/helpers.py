from conftest import TestingSessionLocal

from app.core.auth import hash_password
from app.models.user import User

PASSWORD = "test-password-123"


def login_headers(client, role: str = "manager") -> dict:
    username = f"test_{role}"

    with TestingSessionLocal() as session:
        exists = session.query(User).filter(User.username == username).first()
        if exists is None:
            session.add(
                User(
                    username=username,
                    password_hash=hash_password(PASSWORD),
                    role=role,
                    active=True,
                )
            )
            session.commit()

    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
