"""Failed-login rate limiter behaviour (the suite runs with limit 0)."""

from app.core import ratelimit


def test_login_rate_limit_blocks_after_too_many_failures(client, monkeypatch):
    ratelimit._failures.clear()
    monkeypatch.setattr(ratelimit, "LOGIN_RATE_LIMIT", 3)

    for _ in range(3):
        response = client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "wrong-password-1"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "wrong-password-2"},
    )
    assert blocked.status_code == 429

    ratelimit._failures.clear()


def test_login_rate_limit_is_per_username(client, monkeypatch):
    ratelimit._failures.clear()
    monkeypatch.setattr(ratelimit, "LOGIN_RATE_LIMIT", 1)

    for _ in range(2):
        client.post(
            "/api/auth/login",
            json={"username": "user_a", "password": "wrong-password-1"},
        )

    blocked = client.post(
        "/api/auth/login",
        json={"username": "user_a", "password": "still-wrong"},
    )
    assert blocked.status_code == 429

    # A different username is not affected by user_a's failures.
    other = client.post(
        "/api/auth/login",
        json={"username": "user_b", "password": "wrong-password-1"},
    )
    assert other.status_code == 401

    ratelimit._failures.clear()


def test_successful_login_clears_failures(client, db, monkeypatch):
    from app.core.auth import hash_password
    from app.models.user import User

    ratelimit._failures.clear()
    monkeypatch.setattr(ratelimit, "LOGIN_RATE_LIMIT", 5)

    user = User(
        username="limiter_user",
        password_hash=hash_password("limiter-pass-123"),
        role="viewer",
        active=True,
    )
    db.add(user)
    db.commit()

    for _ in range(4):
        client.post(
            "/api/auth/login",
            json={"username": "limiter_user", "password": "wrong"},
        )

    ok = client.post(
        "/api/auth/login",
        json={"username": "limiter_user", "password": "limiter-pass-123"},
    )
    assert ok.status_code == 200

    # Failures were cleared, so more wrong attempts are allowed again.
    again = client.post(
        "/api/auth/login",
        json={"username": "limiter_user", "password": "wrong"},
    )
    assert again.status_code == 401

    ratelimit._failures.clear()
