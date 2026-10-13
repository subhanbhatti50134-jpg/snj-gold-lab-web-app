"""Hardening headers on every response."""


def test_security_headers_present(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_api_responses_are_not_cached(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
