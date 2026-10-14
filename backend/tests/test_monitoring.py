import logging

from fastapi.testclient import TestClient


def test_health_reports_version_uptime_and_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["application"] == "SNJ Gold Lab"
    assert body["version"] == "1.0.0"
    assert body["uptime_seconds"] >= 0
    assert body["database"]["status"] == "ok"
    assert body["database"]["latency_ms"] >= 0


def test_metrics_requires_admin(client, auth_headers):
    viewer = auth_headers("viewer")
    response = client.get("/api/metrics", headers=viewer)
    assert response.status_code == 403

    admin = auth_headers("admin")
    response = client.get("/api/metrics", headers=admin)
    assert response.status_code == 200


def test_metrics_counts_requests(client, auth_headers):
    admin = auth_headers("admin")
    before = client.get("/api/metrics", headers=admin).json()
    client.get("/health")
    client.get("/api/nonexistent-route-xyz")
    after = client.get("/api/metrics", headers=admin).json()
    # At least the two requests above plus the metrics call itself.
    assert after["total_requests"] >= before["total_requests"] + 3
    assert after["by_status_class"]["2xx"] >= 1
    assert after["by_status_class"]["4xx"] >= 1
    assert "GET" in after["by_method"]


def test_request_logging_emits_structured_line(client, caplog):
    with caplog.at_level(logging.INFO, logger="hisabpro"):
        client.get("/api/definitely-not-a-route")
    messages = [r.message for r in caplog.records if "request method=" in r.message]
    assert any(
        "path=/api/definitely-not-a-route" in m and "status=404" in m for m in messages
    )


def test_unhandled_exception_is_logged_and_masked(client, caplog):
    app = client.app

    @app.get("/api/_boom_test")
    def _boom():
        raise RuntimeError("secret database detail that must not leak")

    try:
        plain = TestClient(app, raise_server_exceptions=False)
        with caplog.at_level(logging.ERROR, logger="hisabpro"):
            response = plain.get("/api/_boom_test")
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
        assert "secret database detail" not in response.text
        errors = [r.message for r in caplog.records if "unhandled error" in r.message]
        assert any("path=/api/_boom_test" in m for m in errors)
        assert any(
            r.exc_info and "secret database detail" in str(r.exc_info[1])
            for r in caplog.records
        )
    finally:
        app.router.routes[:] = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/api/_boom_test"
        ]
