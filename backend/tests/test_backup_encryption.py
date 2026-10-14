"""Phase 14: encrypted backups, retention pruning, restore drill."""

import base64
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

TEST_KEY = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
WRONG_KEY = base64.b64encode(b"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx").decode()


@pytest.fixture
def encrypted_backup_dir(monkeypatch, tmp_path):
    """Point the backup service at a temp dir with encryption enabled."""
    from app.services import backup as backup_service

    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(backup_service, "BACKUP_KEY", TEST_KEY)
    return tmp_path


@pytest.fixture
def retention(monkeypatch):
    """Helper to set retention days / keep-min on the backup service."""
    from app.services import backup as backup_service

    def _set(days: int, keep_min: int):
        monkeypatch.setattr(backup_service, "BACKUP_RETENTION_DAYS", days)
        monkeypatch.setattr(backup_service, "BACKUP_KEEP_MIN", keep_min)

    return _set


def test_encrypt_decrypt_round_trip(encrypted_backup_dir):
    from app.services import backup as backup_service

    plaintext = b'{"format": "snj-gold-lab-backup", "secret": true}'
    ciphertext = backup_service.encrypt_bytes(plaintext)

    assert ciphertext != plaintext
    assert ciphertext.startswith(backup_service.ENCRYPTION_MAGIC)
    # The payload must not appear in the ciphertext.
    assert b"secret" not in ciphertext

    assert backup_service.decrypt_bytes(ciphertext) == plaintext


def test_decrypt_with_wrong_key_raises(encrypted_backup_dir, monkeypatch):
    from app.services import backup as backup_service

    ciphertext = backup_service.encrypt_bytes(b"important data")

    monkeypatch.setattr(backup_service, "BACKUP_KEY", WRONG_KEY)
    with pytest.raises(ValueError, match="wrong key or corrupt file"):
        backup_service.decrypt_bytes(ciphertext)


def test_decrypt_plaintext_file_raises(encrypted_backup_dir):
    from app.services import backup as backup_service

    with pytest.raises(ValueError, match="Not an encrypted backup"):
        backup_service.decrypt_bytes(b'{"plain": true}')


def test_create_json_backup_encrypted(
    encrypted_backup_dir, client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")

    response = client.post("/api/backups/json", headers=admin)
    assert response.status_code == 201

    body = response.json()
    assert body["filename"].endswith(".json.enc")
    assert body["encrypted"] is True

    path = encrypted_backup_dir / body["filename"]
    assert path.is_file()

    # The file on disk must be ciphertext, not readable JSON.
    raw = path.read_bytes()
    assert raw.startswith(b"SNJENC1")
    with pytest.raises((json.JSONDecodeError, UnicodeDecodeError)):
        json.loads(raw.decode("utf-8", errors="strict"))


def test_encrypted_json_backup_restores(
    encrypted_backup_dir, client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")

    # Seed one product, back it up (encrypted), add a second product.
    created = client.post(
        "/api/products",
        json={
            "sku": "ENC-1",
            "name": "Encrypted gold",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 99.99,
        },
        headers=admin,
    )
    assert created.status_code == 201

    backup = client.post("/api/backups/json", headers=admin).json()
    assert backup["encrypted"] is True

    client.post(
        "/api/products",
        json={
            "sku": "ENC-2",
            "name": "Added after backup",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 99.99,
        },
        headers=admin,
    )

    restored = client.post(
        f"/api/backups/json/{backup['filename']}/restore",
        json={"confirm": backup["filename"]},
        headers=admin,
    )
    assert restored.status_code == 200
    assert restored.json()["restored"] is True

    products = client.get("/api/products", headers=admin).json()
    assert any(p["sku"] == "ENC-1" for p in products)
    assert not any(p["sku"] == "ENC-2" for p in products)


def test_plaintext_backup_still_restores_with_encryption_enabled(
    encrypted_backup_dir, client: TestClient, db: Session, auth_headers
):
    """An old unencrypted backup must remain restorable after the
    encryption key is configured."""
    from app.services import backup as backup_service

    admin = auth_headers("admin")

    client.post(
        "/api/products",
        json={
            "sku": "PLAIN-1",
            "name": "Plaintext era",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 99.99,
        },
        headers=admin,
    )

    # Write a plaintext backup manually (simulating a pre-encryption file).
    # Temporarily disable encryption for the write.
    backup_service.BACKUP_KEY = ""
    legacy = client.post("/api/backups/json", headers=admin).json()
    assert legacy["filename"].endswith(".json")
    assert legacy["encrypted"] is False

    # Re-enable encryption; the legacy file must still restore.
    backup_service.BACKUP_KEY = TEST_KEY

    client.post(
        "/api/products",
        json={
            "sku": "PLAIN-2",
            "name": "After legacy backup",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 99.99,
        },
        headers=admin,
    )

    restored = client.post(
        f"/api/backups/json/{legacy['filename']}/restore",
        json={"confirm": legacy["filename"]},
        headers=admin,
    )
    assert restored.status_code == 200

    products = client.get("/api/products", headers=admin).json()
    assert any(p["sku"] == "PLAIN-1" for p in products)
    assert not any(p["sku"] == "PLAIN-2" for p in products)


def test_restore_encrypted_backup_with_wrong_key_fails_cleanly(
    encrypted_backup_dir, client: TestClient, db: Session, auth_headers, monkeypatch
):
    from app.services import backup as backup_service

    admin = auth_headers("admin")

    backup = client.post("/api/backups/json", headers=admin).json()
    assert backup["encrypted"] is True

    # Simulate a lost/changed key.
    monkeypatch.setattr(backup_service, "BACKUP_KEY", WRONG_KEY)

    restored = client.post(
        f"/api/backups/json/{backup['filename']}/restore",
        json={"confirm": backup["filename"]},
        headers=admin,
    )
    assert restored.status_code == 500
    assert "decrypt" in restored.json()["detail"].lower()


def test_prune_keeps_newest_and_deletes_expired(encrypted_backup_dir, retention):
    from app.services import backup as backup_service

    retention(days=30, keep_min=3)
    now = time.time()

    # 8 files: 3 recent, 5 older than the 30-day cutoff.
    for i in range(8):
        age_days = i if i < 3 else 40 + i
        path = encrypted_backup_dir / f"snj-gold-lab-{i:04d}.json"
        path.write_text("{}")
        old = now - (age_days * 86400)
        os.utime(path, (old, old))

    deleted = backup_service.prune_old_backups()

    remaining = sorted(p.name for p in encrypted_backup_dir.iterdir())
    # The 3 newest (i=0,1,2) survive regardless; the 5 old ones (i>=3) go.
    assert len(deleted) == 5
    assert remaining == [
        "snj-gold-lab-0000.json",
        "snj-gold-lab-0001.json",
        "snj-gold-lab-0002.json",
    ]


def test_prune_never_deletes_below_keep_min(tmp_path, monkeypatch, retention):
    from app.services import backup as backup_service

    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)
    retention(days=30, keep_min=5)

    now = time.time()
    # 10 files, ALL older than the cutoff.
    for i in range(10):
        path = tmp_path / f"old-{i:04d}.json"
        path.write_text("{}")
        old = now - (90 * 86400)
        os.utime(path, (old, old))

    deleted = backup_service.prune_old_backups()

    # keep-min is 5: 10 - 5 = 5 deleted, 5 kept.
    assert len(deleted) == 5
    assert len(list(tmp_path.iterdir())) == 5


def test_create_json_backup_triggers_prune(
    encrypted_backup_dir, client: TestClient, db: Session, auth_headers, retention
):
    from app.services import backup as backup_service

    admin = auth_headers("admin")
    retention(days=30, keep_min=5)

    # Plant 6 expired files plus keep the dir non-empty.
    now = time.time()
    for i in range(6):
        path = encrypted_backup_dir / f"expired-{i:04d}.json"
        path.write_text("{}")
        old = now - (60 * 86400)
        os.utime(path, (old, old))

    # keep-min 5: of the 6 expired + 1 new = 7 files, the newest
    # 5 survive; 2 oldest expired files are pruned.
    response = client.post("/api/backups/json", headers=admin)
    assert response.status_code == 201

    remaining = [p.name for p in encrypted_backup_dir.iterdir()]
    # The 6 expired + 1 new = 7; keep-min 5 means 2 oldest expired pruned.
    assert len(remaining) == 5
    assert response.json()["filename"] in remaining


def test_full_restore_drill_preserves_amounts_and_counts(
    encrypted_backup_dir, client: TestClient, db: Session, auth_headers
):
    """Backup -> wipe -> restore must reproduce exact row counts and
    decimal amounts. This is the Phase 14 restore drill."""
    admin = auth_headers("admin")

    # Seed a product, a purchase with a known decimal amount, and a payment.
    product = client.post(
        "/api/products",
        json={
            "sku": "DRILL-1",
            "name": "Drill gold",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 100,
        },
        headers=admin,
    ).json()

    purchase = client.post(
        "/api/purchases",
        json={
            "product_id": product["id"],
            "quantity_grams": "2.5000",
            "gross_weight_grams": "2.5000",
            "net_weight_grams": "2.5000",
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": "3333.3350",
            "charges": "0.07",
            "amount_paid": "4000.00",
            "payment_method": "cash",
            "party_name": "Drill Supplier",
            "location": "Main Store",
            "created_by": "admin",
        },
        headers=admin,
    )
    assert purchase.status_code == 201, purchase.text
    expected_total = purchase.json()["total_amount"]

    # Record counts before the backup.
    def snapshot():
        return {
            "products": len(client.get("/api/products", headers=admin).json()),
            "transactions": len(
                client.get("/api/transactions", headers=admin).json()
            ),
            "payments": len(
                client.get(
                    f"/api/transactions/{purchase.json()['id']}/payments",
                    headers=admin,
                ).json()
            ),
        }

    before = snapshot()
    assert before["products"] >= 1
    assert before["transactions"] >= 1

    # Backup (encrypted), then add MORE data that restore must remove.
    backup = client.post("/api/backups/json", headers=admin).json()
    assert backup["encrypted"] is True

    # Add a product and a purchase AFTER the backup.
    client.post(
        "/api/products",
        json={
            "sku": "DRILL-AFTER",
            "name": "Added after backup",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 100,
        },
        headers=admin,
    )
    after_add = snapshot()
    assert after_add["products"] == before["products"] + 1

    # Restore the encrypted backup: the extra product must vanish and
    # every original count and amount must come back exactly.
    restored = client.post(
        f"/api/backups/json/{backup['filename']}/restore",
        json={"confirm": backup["filename"]},
        headers=admin,
    )
    assert restored.status_code == 200

    after = snapshot()
    assert after == before

    # The purchase total must be byte-identical after the round trip.
    txns = client.get("/api/transactions", headers=admin).json()
    txn = next(t for t in txns if t["id"] == purchase.json()["id"])
    assert txn["total_amount"] == expected_total
    assert txn["rate_per_gram"] == "3333.3350"
