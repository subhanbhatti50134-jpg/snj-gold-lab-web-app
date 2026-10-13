"""Insert demo data so the app is usable right after setup.

Creates demo users, products, verified rates, parties and a few
transactions with payments. Safe to run once: it stops when products
already exist.

    .venv/bin/python scripts/seed_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.core.auth import hash_password
from app.db.session import SessionLocal
from app.models.metal_rate import MetalRate
from app.models.product import Product
from app.models.user import User
from app.schemas.party import PartyCreate
from app.schemas.payments import PaymentCreate
from app.schemas.transaction import TransactionCreate
from app.services.parties import create_party
from app.services.payments import record_payment
from app.services.pricing import normalize_rate
from app.services.transactions import create_transaction

DEMO_PASSWORD = "DemoPass!1234"
SEED_USER = "seed"


def ensure_user(db, username: str, role: str) -> None:
    if db.scalar(select(User.id).where(User.username == username)):
        return

    db.add(
        User(
            username=username,
            password_hash=hash_password(DEMO_PASSWORD),
            role=role,
            active=True,
        )
    )
    db.commit()
    print(f"  user {username} ({role}) created")


def ensure_product(db, **kwargs) -> Product:
    product = db.scalar(
        select(Product).where(Product.sku == kwargs["sku"])
    )
    if product:
        return product

    product = Product(**kwargs)
    db.add(product)
    db.commit()
    db.refresh(product)
    print(f"  product {product.sku} ({product.name}) created")
    return product


def ensure_rate(db, metal: str, purity: Decimal, per_tola: Decimal,
                unit: str, note: str) -> None:
    exists = db.scalar(
        select(MetalRate.id).where(
            MetalRate.metal == metal,
            MetalRate.purity == purity,
            MetalRate.active.is_(True),
        )
    )
    if exists:
        return

    entered = per_tola
    per_gram = normalize_rate(entered, unit)

    db.add(
        MetalRate(
            metal=metal,
            purity=purity,
            rate_per_gram=per_gram,
            unit=unit,
            entered_rate=entered,
            source_note=note,
            verified_by=SEED_USER,
            active=True,
        )
    )
    db.commit()
    print(f"  rate {metal} {purity}%: {entered} per {unit}")


def ensure_party(db, name: str, kind: str, phone: str):
    from app.models.party import Party

    party = db.scalar(select(Party).where(Party.name == name))
    if party:
        return party

    party = create_party(
        db,
        PartyCreate(name=name, kind=kind, phone=phone),
        SEED_USER,
    )
    print(f"  party {name} ({kind}) created")
    return party


def tx_kwargs(product: Product, **overrides) -> dict:
    base = {
        "product_id": product.id,
        "quantity_grams": Decimal("10"),
        "gross_weight_grams": Decimal("10.5"),
        "net_weight_grams": Decimal("10"),
        "deduction_grams": Decimal("0.5"),
        "purity": product.purity,
        "amount_paid": Decimal("0"),
        "location": "Main Store",
        "created_by": SEED_USER,
    }
    base.update(overrides)
    return base


def main() -> None:
    with SessionLocal() as db:
        if db.scalar(select(Product.id)):
            print("STOP: products already exist; refusing to seed twice.")
            print("No changes were made.")
            return

        print("Seeding demo data…")

        for username, role in (
            ("manager", "manager"),
            ("operator", "operator"),
            ("viewer", "viewer"),
        ):
            ensure_user(db, username, role)

        gold24 = ensure_product(
            db, sku="GOLD-24K", name="Gold 24K bar",
            category="loose_metal", metal="gold",
            purity=Decimal("99.99"), active=True,
        )
        gold22 = ensure_product(
            db, sku="GOLD-22K", name="Gold 22K necklace",
            category="jewellery", metal="gold",
            purity=Decimal("91.60"), active=True,
        )
        silver = ensure_product(
            db, sku="SILVER-999", name="Silver 999 bar",
            category="loose_metal", metal="silver",
            purity=Decimal("99.90"), active=True,
        )
        ensure_product(
            db, sku="LAB-AU-STD", name="Gold standard (lab)",
            category="laboratory_material", metal="gold",
            purity=Decimal("99.99"), active=True,
        )

        ensure_rate(db, "gold", Decimal("99.99"), Decimal("24000"),
                    "tola", "seed: market rate")
        ensure_rate(db, "gold", Decimal("91.60"), Decimal("22100"),
                    "tola", "seed: market rate")
        ensure_rate(db, "silver", Decimal("99.90"), Decimal("3050"),
                    "tola", "seed: market rate")

        customer = ensure_party(db, "Ali Jewellers", "customer",
                                "0300-1234567")
        supplier = ensure_party(db, "Karachi Metals", "supplier",
                                "0321-7654321")

        # Two purchases (stock in) with a partial payment on the first.
        buy1 = create_transaction(
            db,
            TransactionCreate(**tx_kwargs(
                gold24,
                party_id=customer.id,
                quantity_grams=Decimal("100"),
                gross_weight_grams=Decimal("101"),
                net_weight_grams=Decimal("100"),
                deduction_grams=Decimal("1"),
                amount_paid=Decimal("200000"),
                rate_per_gram=Decimal("24000"),
                rate_unit="tola",
                charges=Decimal("500"),
                notes="seed purchase",
            )),
            "purchase",
        )
        create_transaction(
            db,
            TransactionCreate(**tx_kwargs(
                silver,
                party_id=supplier.id,
                quantity_grams=Decimal("500"),
                gross_weight_grams=Decimal("505"),
                net_weight_grams=Decimal("500"),
                deduction_grams=Decimal("5"),
                amount_paid=Decimal("0"),
                rate_per_gram=Decimal("3050"),
                rate_unit="tola",
                notes="seed purchase",
            )),
            "purchase",
        )

        create_transaction(
            db,
            TransactionCreate(**tx_kwargs(
                gold22,
                party_id=supplier.id,
                quantity_grams=Decimal("50"),
                gross_weight_grams=Decimal("50.5"),
                net_weight_grams=Decimal("50"),
                deduction_grams=Decimal("0.5"),
                amount_paid=Decimal("0"),
                rate_per_gram=Decimal("22100"),
                rate_unit="tola",
                notes="seed purchase",
            )),
            "purchase",
        )

        # Two sales: one mostly paid, one on credit (due amount).
        create_transaction(
            db,
            TransactionCreate(**tx_kwargs(
                gold22,
                party_id=customer.id,
                quantity_grams=Decimal("20"),
                gross_weight_grams=Decimal("21"),
                net_weight_grams=Decimal("20"),
                deduction_grams=Decimal("1"),
                amount_paid=Decimal("30000"),
                rate_per_gram=Decimal("22100"),
                rate_unit="tola",
                notes="seed sale (paid)",
            )),
            "sale",
        )
        sale_due = create_transaction(
            db,
            TransactionCreate(**tx_kwargs(
                gold24,
                party_id=customer.id,
                quantity_grams=Decimal("40"),
                gross_weight_grams=Decimal("41"),
                net_weight_grams=Decimal("40"),
                deduction_grams=Decimal("1"),
                amount_paid=Decimal("0"),
                rate_per_gram=Decimal("24000"),
                rate_unit="tola",
                notes="seed sale (on credit)",
            )),
            "sale",
        )

        # A part payment against the credit sale.
        record_payment(
            db,
            sale_due.id,
            PaymentCreate(
                amount=Decimal("30000"),
                method="bank_transfer",
                note="seed part payment",
                recorded_by=SEED_USER,
            ),
        )

        print(f"\nDemo data ready at {datetime.now():%Y-%m-%d %H:%M}")
        print(f"Products, rates, 2 parties, 3 purchases, 2 sales, 1 payment.")
        print(f"\nDemo logins (password: {DEMO_PASSWORD}):")
        print("  manager / operator / viewer  (plus your admin account)")


if __name__ == "__main__":
    main()
