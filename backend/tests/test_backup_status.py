from datetime import UTC, datetime, timedelta

from helpers import login_headers

from app.models.audit import AuditLog


def test_status_requires_login(client):
    assert client.get("/api/backups/status").status_code == 401


def test_status_is_admin_only(client):
    response = client.get(
        "/api/backups/status", headers=login_headers(client, "manager")
    )
    assert response.status_code == 403


def test_never_backed_up_is_overdue(client):
    response = client.get(
        "/api/backups/status", headers=login_headers(client, "admin")
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["last_backup_at"] is None
    assert data["overdue"] is True
    assert data["age_days"] is None
    assert data["threshold_days"] == 7


def test_fresh_backup_is_not_overdue(client):
    created = client.post(
        "/api/backups/json", headers=login_headers(client, "admin")
    )
    assert created.status_code == 201, created.text

    data = client.get(
        "/api/backups/status", headers=login_headers(client, "admin")
    ).json()
    assert data["overdue"] is False
    assert data["age_days"] == 0
    assert data["last_backup_at"] is not None


def test_stale_backup_becomes_overdue(client, db):
    created = client.post(
        "/api/backups/json", headers=login_headers(client, "admin")
    )
    assert created.status_code == 201, created.text

    # Age the audit row past the 7-day threshold.
    entry = (
        db.query(AuditLog)
        .filter(AuditLog.action == "backup.create.json")
        .one()
    )
    entry.created_at = datetime.now(UTC) - timedelta(days=10)
    db.commit()

    data = client.get(
        "/api/backups/status", headers=login_headers(client, "admin")
    ).json()
    assert data["overdue"] is True
    assert data["age_days"] >= 10
