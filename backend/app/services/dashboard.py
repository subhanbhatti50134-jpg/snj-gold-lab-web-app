from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.metal_rate import MetalRate
from app.models.party import Party
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.transaction import Transaction
from app.services.pricing import money

ZERO = Decimal("0.00")


def get_dashboard(db: Session) -> dict:
    """Overview numbers, always computed from authoritative records."""
    balances = db.execute(
        select(
            StockMovement.product_id,
            func.coalesce(func.sum(StockMovement.quantity_delta_grams), 0),
        ).group_by(StockMovement.product_id)
    ).all()

    stock_grams = Decimal("0")
    stock_by_product: dict[int, Decimal] = {}

    for product_id, balance in balances:
        value = Decimal(str(balance))
        if value != 0:
            stock_grams += value
            stock_by_product[product_id] = value

    products = {
        product.id: product
        for product in db.scalars(select(Product)).all()
    }

    rates = list(
        db.scalars(
            select(MetalRate).where(MetalRate.active.is_(True))
        ).all()
    )
    rate_map = {(rate.metal, str(rate.purity)): rate for rate in rates}

    inventory_value = ZERO
    unvalued = []

    for product_id, balance in stock_by_product.items():
        product = products.get(product_id)
        if product is None:
            continue

        rate = rate_map.get((product.metal, str(product.purity)))

        if rate is None:
            unvalued.append(
                {
                    "product_id": product.id,
                    "name": product.name,
                    "balance_grams": balance,
                }
            )
            continue

        inventory_value += money(
            balance * Decimal(str(rate.rate_per_gram))
        )

    totals: dict[str, dict[str, Decimal]] = {}

    for kind in ("purchase", "sale"):
        total, paid = db.execute(
            select(
                func.coalesce(func.sum(Transaction.total_amount), 0),
                func.coalesce(func.sum(Transaction.amount_paid), 0),
            ).where(
                Transaction.kind == kind,
                Transaction.status == "active",
            )
        ).one()
        totals[kind] = {
            "total_amount": money(Decimal(str(total))),
            "amount_paid": money(Decimal(str(paid))),
            "remaining_amount": money(
                Decimal(str(total)) - Decimal(str(paid))
            ),
        }

    product_count = db.scalar(
        select(func.count())
        .select_from(Product)
        .where(Product.active.is_(True))
    )
    party_count = db.scalar(
        select(func.count()).select_from(Party).where(Party.active.is_(True))
    )
    transaction_count = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.status == "active")
    )

    recent = db.scalars(
        select(Transaction)
        .where(Transaction.status == "active")
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .limit(8)
    ).all()

    return {
        "stock_grams": stock_grams,
        "product_count": int(product_count or 0),
        "party_count": int(party_count or 0),
        "transaction_count": int(transaction_count or 0),
        "inventory_value": inventory_value,
        "unvalued_products": unvalued,
        "purchases": totals["purchase"],
        "sales": totals["sale"],
        "active_rates": [
            {
                "id": rate.id,
                "metal": rate.metal,
                "purity": rate.purity,
                "rate_per_gram": rate.rate_per_gram,
                "unit": rate.unit,
                "entered_rate": rate.entered_rate,
            }
            for rate in sorted(
                rates, key=lambda r: (r.metal, str(r.verified_at)), reverse=True
            )
        ],
        "recent_transactions": [
            {
                "id": tx.id,
                "reference": tx.reference,
                "kind": tx.kind,
                "product_id": tx.product_id,
                "party_name": tx.party_name,
                "quantity_grams": tx.quantity_grams,
                "total_amount": tx.total_amount,
                "amount_paid": tx.amount_paid,
                "created_at": tx.created_at,
            }
            for tx in recent
        ],
    }
