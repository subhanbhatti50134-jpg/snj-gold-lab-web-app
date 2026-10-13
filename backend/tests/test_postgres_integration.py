"""PostgreSQL-specific integration tests.

SQLite unit tests do not prove PostgreSQL compatibility. These tests
reconnect to the real PostgreSQL database configured in the project
.env file, but they work inside an isolated schema (hisabpro_test) so
development data in the public schema is never touched.

Run them with:

    HISABPRO_PG_TESTS=1 .venv/bin/python -m pytest tests -q

They are skipped unless HISABPRO_PG_TESTS=1 is set.
"""
import os
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from conftest import PG_DATABASE_URL

PG_ENABLED = os.getenv("HISABPRO_PG_TESTS") == "1"
SCHEMA = "hisabpro_test"

pytestmark = pytest.mark.skipif(
    not PG_ENABLED or not PG_DATABASE_URL.startswith("postgresql"),
    reason="Set HISABPRO_PG_TESTS=1 with a real DATABASE_URL to run",
)


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(
        PG_DATABASE_URL,
        poolclass=NullPool,
        connect_args={"options": f"-csearch_path={SCHEMA}"},
    )

    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))

    yield engine

    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))

    engine.dispose()


@pytest.fixture
def pg_session_factory(pg_engine):
    from app.db.base import Base
    import app.models  # noqa: F401

    Base.metadata.drop_all(bind=pg_engine)
    Base.metadata.create_all(bind=pg_engine)

    factory = sessionmaker(
        bind=pg_engine, autoflush=False, expire_on_commit=False
    )
    yield factory

    Base.metadata.drop_all(bind=pg_engine)


@pytest.fixture
def pg_client(pg_session_factory):
    from app.db.session import get_db
    from app.main import app

    def override_get_db():
        db = pg_session_factory()
        try:
            yield db
        finally:
            db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


@pytest.fixture
def pg_admin_headers(pg_client, pg_session_factory):
    from app.core.auth import hash_password
    from app.models.user import User

    with pg_session_factory() as db:
        db.add(
            User(
                username="pg_admin",
                password_hash=hash_password("pg-test-password-123"),
                role="admin",
                active=True,
            )
        )
        db.commit()

    response = pg_client.post(
        "/api/auth/login",
        json={"username": "pg_admin", "password": "pg-test-password-123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_product(client, headers, sku="PG-GOLD-001"):
    response = client.post(
        "/api/products",
        headers=headers,
        json={
            "sku": sku,
            "name": "PG Test Gold",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 100,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _purchase(client, headers, product_id, weight, amount_paid=0):
    response = client.post(
        "/api/purchases",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity_grams": weight,
            "gross_weight_grams": weight,
            "net_weight_grams": weight,
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": 100,
            "charges": 0,
            "amount_paid": amount_paid,
            "payment_method": "cash",
            "party_name": "PG Supplier",
            "location": "Main Store",
            "created_by": "pg_admin",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_pg_login_and_me(pg_client, pg_admin_headers):
    me = pg_client.get("/api/auth/me", headers=pg_admin_headers)
    assert me.status_code == 200, me.text
    assert me.json()["username"] == "pg_admin"
    assert me.json()["role"] == "admin"


def test_pg_numeric_precision_is_exact(pg_client, pg_admin_headers):
    """Financial amounts must round-trip without binary float drift."""
    product = _create_product(pg_client, pg_admin_headers)

    # 3 grams at 3333.335/g with 0.07 charges.
    response = pg_client.post(
        "/api/purchases",
        headers=pg_admin_headers,
        json={
            "product_id": product["id"],
            "quantity_grams": "3.0000",
            "gross_weight_grams": "3.0000",
            "net_weight_grams": "3.0000",
            "deduction_grams": 0,
            "purity": 100,
            "rate_per_gram": "3333.3350",
            "charges": "0.07",
            "amount_paid": 0,
            "payment_method": "cash",
            "party_name": "PG Supplier",
            "location": "Main Store",
            "created_by": "pg_admin",
        },
    )
    assert response.status_code == 201, response.text

    # 3 * 3333.335 = 9999.99... + 0.07, rounded half-up to 10000.06?
    # 3 * 3333.335 = 10000.005 exactly in decimal -> 10000.01 after
    # quantize, + 0.07 = 10000.08.
    assert Decimal(response.json()["total_amount"]) == Decimal("10000.08")


def test_pg_duplicate_sku_enforced_by_database(pg_client, pg_admin_headers):
    _create_product(pg_client, pg_admin_headers, sku="PG-DUP-001")

    duplicate = pg_client.post(
        "/api/products",
        headers=pg_admin_headers,
        json={
            "sku": "PG-DUP-001",
            "name": "Duplicate",
            "category": "loose_metal",
            "metal": "gold",
            "purity": 100,
        },
    )
    assert duplicate.status_code == 409


def test_pg_full_business_flow(pg_client, pg_admin_headers):
    product = _create_product(pg_client, pg_admin_headers)

    # Verified tola rate: 116638/tola == 10000/g.
    rate = pg_client.post(
        "/api/rates",
        headers=pg_admin_headers,
        json={
            "metal": "gold",
            "purity": 100,
            "rate_per_gram": 116638,
            "unit": "tola",
            "verified_by": "pg_admin",
        },
    )
    assert rate.status_code == 201, rate.text

    party = pg_client.post(
        "/api/parties",
        headers=pg_admin_headers,
        json={"name": "PG Customer", "kind": "customer"},
    )
    assert party.status_code == 201, party.text

    purchase = _purchase(pg_client, pg_admin_headers, product["id"], 10, 1000)
    assert Decimal(purchase["total_amount"]) == Decimal("1000.00")

    sale_payload = {
        "product_id": product["id"],
        "party_id": party.json()["id"],
        "quantity_grams": 4,
        "gross_weight_grams": 4,
        "net_weight_grams": 4,
        "deduction_grams": 0,
        "purity": 100,
        "amount_paid": 20000,
        "payment_method": "cash",
        "location": "Main Store",
        "created_by": "pg_admin",
    }
    sale = pg_client.post("/api/sales", headers=pg_admin_headers, json=sale_payload)
    assert sale.status_code == 201, sale.text
    assert Decimal(sale.json()["total_amount"]) == Decimal("40000.00")
    assert sale.json()["party_name"] == "PG Customer"

    # Partial payment against the remaining 20000.
    payment = pg_client.post(
        f"/api/transactions/{sale.json()['id']}/payments",
        headers=pg_admin_headers,
        json={
            "amount": 15000,
            "method": "bank_transfer",
            "note": "PG partial payment",
            "recorded_by": "pg_admin",
        },
    )
    assert payment.status_code == 201, payment.text

    # Transfer 2 grams to the annex, then return 1 from the sale.
    transfer = pg_client.post(
        "/api/movements/transfers",
        headers=pg_admin_headers,
        json={
            "product_id": product["id"],
            "quantity_grams": 2,
            "from_location": "Main Store",
            "to_location": "Annex",
            "created_by": "pg_admin",
        },
    )
    assert transfer.status_code == 201, transfer.text

    returned = pg_client.post(
        "/api/movements/sales-returns",
        headers=pg_admin_headers,
        json={
            "original_sale_id": sale.json()["id"],
            "quantity_grams": 1,
            "created_by": "pg_admin",
        },
    )
    assert returned.status_code == 201, returned.text

    inventory = {
        row["location"]: Decimal(row["balance_grams"])
        for row in pg_client.get(
            "/api/inventory", headers=pg_admin_headers
        ).json()
        if row["product_id"] == product["id"]
    }
    # 10 in - 4 sold + 1 returned = 7 at Main, 2 at Annex.
    assert inventory["Main Store"] == Decimal("5")
    assert inventory["Annex"] == Decimal("2")

    parties = pg_client.get(
        "/api/parties", headers=pg_admin_headers
    ).json()
    receivable = [
        row for row in parties if row["name"] == "PG Customer"
    ][0]["receivable"]
    # 40000 sale - 35000 paid - 10000 returned goods = -5000
    # (the customer is owed 5000, which a refund or credit can settle).
    assert Decimal(str(receivable)) == Decimal("-5000.00")

    # Cancel the return; stock returns to 6 at Main.
    cancel_return = pg_client.post(
        f"/api/transactions/{returned.json()['id']}/cancel",
        headers=pg_admin_headers,
        json={"reason": "PG integration cancel test"},
    )
    assert cancel_return.status_code == 200, cancel_return.text

    inventory = {
        row["location"]: Decimal(row["balance_grams"])
        for row in pg_client.get(
            "/api/inventory", headers=pg_admin_headers
        ).json()
        if row["product_id"] == product["id"]
    }
    assert inventory["Main Store"] == Decimal("4")

    # Audit trail exists for the whole flow.
    audit = pg_client.get(
        "/api/audit",
        params={"limit": 500},
        headers=pg_admin_headers,
    ).json()
    actions = {entry["action"] for entry in audit}
    assert "product.create" in actions
    assert "rate.create" in actions
    assert "purchase.create" in actions
    assert "payment.create" in actions
    assert "stock_transfer.create" in actions
    assert "transaction.cancel" in actions


def test_pg_concurrent_sales_cannot_oversell(
    pg_client, pg_admin_headers, pg_session_factory
):
    """Row locks must serialize two sales of the last gram."""
    product = _create_product(pg_client, pg_admin_headers)
    _purchase(pg_client, pg_admin_headers, product["id"], 1)

    from app.schemas.transaction import TransactionCreate
    from app.services.transactions import create_transaction

    def attempt():
        with pg_session_factory() as db:
            try:
                payload = TransactionCreate(
                    product_id=product["id"],
                    quantity_grams=Decimal("1"),
                    gross_weight_grams=Decimal("1"),
                    net_weight_grams=Decimal("1"),
                    deduction_grams=Decimal("0"),
                    purity=Decimal("100"),
                    rate_per_gram=Decimal("100"),
                    created_by="pg_admin",
                    location="Main Store",
                )
                create_transaction(db, payload, "sale")
                return "ok"
            except Exception as exc:  # noqa: BLE001
                return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))

    successes = [r for r in results if r == "ok"]
    failures = [r for r in results if r != "ok"]

    assert len(successes) == 1, results
    assert len(failures) == 1, results
    assert "Insufficient stock" in failures[0]

    inventory = pg_client.get(
        "/api/inventory", headers=pg_admin_headers
    ).json()
    total = sum(
        Decimal(row["balance_grams"])
        for row in inventory
        if row["product_id"] == product["id"]
    )
    assert total == Decimal("0")
