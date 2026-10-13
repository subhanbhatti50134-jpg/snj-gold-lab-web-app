import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def create_product(
    client: TestClient, headers: dict, sku: str, name: str
) -> dict:
    response = client.post(
        "/api/products",
        json={
            "sku": sku,
            "name": name,
            "category": "loose_metal",
            "metal": "gold",
            "purity": 99.99,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_json_backup_and_restore_round_trip(
    client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")

    # Seed data through the API so the whole stack is exercised.
    create_product(client, admin, "JB-1", "JSON backup gold")

    created = client.post("/api/backups/json", headers=admin)
    assert created.status_code == 201

    body = created.json()
    assert body["kind"] == "json"
    assert body["filename"].endswith(".json")
    assert body["counts"]["products"] >= 1

    # Add a product AFTER the backup; restore must remove it again.
    create_product(client, admin, "JB-2", "Product after backup")

    before_restore = client.get("/api/products", headers=admin).json()
    assert any(p["sku"] == "JB-2" for p in before_restore)

    restored = client.post(
        f"/api/backups/json/{body['filename']}/restore",
        json={"confirm": body["filename"]},
        headers=admin,
    )
    assert restored.status_code == 200
    assert restored.json()["restored"] is True

    after_restore = client.get("/api/products", headers=admin).json()
    assert any(p["sku"] == "JB-1" for p in after_restore)
    assert not any(p["sku"] == "JB-2" for p in after_restore)

    # The admin user must survive the restore (it was in the backup),
    # otherwise the whole system would lock everyone out.
    me = client.get("/api/auth/me", headers=admin)
    assert me.status_code == 200


def test_json_backup_preserves_transaction_amounts(
    client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")

    product = create_product(client, admin, "JB-3", "Round trip metal")

    # A purchase with a known decimal total: 5 g x 3000/g x 100% = 15000.
    purchase = client.post(
        "/api/purchases",
        json={
            "product_id": product["id"],
            "quantity_grams": 5,
            "gross_weight_grams": 5,
            "net_weight_grams": 5,
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": 3000,
            "rate_unit": "gram",
            "amount_paid": 15000,
            "location": "Main Store",
        },
        headers=admin,
    )
    assert purchase.status_code == 201
    total_before = purchase.json()["total_amount"]

    created = client.post("/api/backups/json", headers=admin).json()

    restored = client.post(
        f"/api/backups/json/{created['filename']}/restore",
        json={"confirm": created["filename"]},
        headers=admin,
    )
    assert restored.status_code == 200

    transactions = client.get("/api/transactions", headers=admin).json()
    match = [t for t in transactions if t["id"] == purchase.json()["id"]]
    assert match, "restored transaction is missing"
    # Amounts survive the JSON round trip without float drift.
    assert float(match[0]["total_amount"]) == float(total_before)


def test_json_backup_restore_keeps_payments_linked_to_transactions(
    client: TestClient, db: Session, auth_headers
):
    """Restore must re-insert transactions before their payments.

    On PostgreSQL this guards the foreign key ordering: payments reference
    transactions.id, so a restore that flushed payments first would fail
    with a ForeignKeyViolation. SQLite does not enforce FKs by default, so
    this test is only meaningful on the PostgreSQL integration run.
    """
    admin = auth_headers("admin")

    product = create_product(client, admin, "JB-FK", "FK ordering metal")

    # A purchase adds stock so the sale below has something to sell.
    purchase = client.post(
        "/api/purchases",
        json={
            "product_id": product["id"],
            "quantity_grams": 10,
            "gross_weight_grams": 10,
            "net_weight_grams": 10,
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": 3000,
            "rate_unit": "gram",
            "amount_paid": 30000,
            "location": "Main Store",
        },
        headers=admin,
    )
    assert purchase.status_code == 201

    # A sale with a partial payment creates a transaction + a payment row.
    sale = client.post(
        "/api/sales",
        json={
            "product_id": product["id"],
            "quantity_grams": 5,
            "gross_weight_grams": 5,
            "net_weight_grams": 5,
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": 3000,
            "rate_unit": "gram",
            "amount_paid": 10000,
            "location": "Main Store",
        },
        headers=admin,
    )
    assert sale.status_code == 201
    sale_id = sale.json()["id"]

    created = client.post("/api/backups/json", headers=admin).json()
    assert created["counts"]["transactions"] >= 1
    assert created["counts"]["payments"] >= 1

    # Restore over the live data. If payments were flushed before their
    # parent transactions, PostgreSQL would reject the insert.
    restored = client.post(
        f"/api/backups/json/{created['filename']}/restore",
        json={"confirm": created["filename"]},
        headers=admin,
    )
    assert restored.status_code == 200
    assert restored.json()["restored"] is True

    # The sale and its payment must both survive, still linked.
    transactions = client.get("/api/transactions", headers=admin).json()
    match = [t for t in transactions if t["id"] == sale_id]
    assert match, "restored sale is missing"
    assert float(match[0]["amount_paid"]) == 10000.0


def test_json_backup_download(
    client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")

    created = client.post("/api/backups/json", headers=admin).json()

    download = client.get(
        f"/api/backups/json/{created['filename']}/download",
        headers=admin,
    )
    assert download.status_code == 200

    payload = json.loads(download.content)
    assert payload["format"] == "snj-gold-lab-backup"
    assert payload["version"] == 1
    assert "users" in payload["data"]
    assert "transactions" in payload["data"]


def test_json_backup_requires_matching_confirm(
    client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")

    created = client.post("/api/backups/json", headers=admin).json()

    wrong = client.post(
        f"/api/backups/json/{created['filename']}/restore",
        json={"confirm": "wrong-name.json"},
        headers=admin,
    )
    assert wrong.status_code == 422


def test_json_backup_rejects_invalid_file(
    client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")

    # A .json file that is NOT a valid backup must be refused.
    from app.services.backup import BACKUP_DIR

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    bad = BACKUP_DIR / "not-a-backup.json"
    bad.write_text(json.dumps({"hello": "world"}), encoding="utf-8")

    try:
        restored = client.post(
            "/api/backups/json/not-a-backup.json/restore",
            json={"confirm": "not-a-backup.json"},
            headers=admin,
        )
        assert restored.status_code == 422
    finally:
        bad.unlink(missing_ok=True)


def test_json_backup_forbidden_for_non_admin(
    client: TestClient, db: Session, auth_headers
):
    for role in ("manager", "operator", "viewer"):
        response = client.post("/api/backups/json", headers=auth_headers(role))
        assert response.status_code == 403, role


def test_backups_list_includes_json_files(
    client: TestClient, db: Session, auth_headers
):
    admin = auth_headers("admin")

    created = client.post("/api/backups/json", headers=admin).json()

    rows = client.get("/api/backups", headers=admin).json()
    names = {row["filename"]: row for row in rows}
    assert created["filename"] in names
    assert names[created["filename"]]["kind"] == "json"
