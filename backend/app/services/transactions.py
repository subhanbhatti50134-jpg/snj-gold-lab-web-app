
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.metal_rate import MetalRate
from app.models.payments import Payment
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate
from app.services.inventory import get_stock_balance
from app.services.pricing import calculate_total


def create_transaction(
    db: Session,
    payload: TransactionCreate,
    kind: str,
) -> Transaction:
    if kind not in {"purchase", "sale"}:
        raise HTTPException(status_code=400, detail="Invalid transaction type")

    # Lock the product row before checking stock, serializing sales
    # for the same product on databases that support row-level locks.
    product = db.scalar(
        select(Product)
        .where(Product.id == payload.product_id)
        .with_for_update()
    )
    if product is None or not product.active:
        raise HTTPException(status_code=404, detail="Active product not found")

    rate = None
    rate_per_gram = payload.rate_per_gram

    if payload.rate_id is not None:
        rate = db.get(MetalRate, payload.rate_id)
        if rate is None or not rate.active:
            raise HTTPException(status_code=422, detail="Active metal rate not found")
        if rate.metal != product.metal:
            raise HTTPException(status_code=422, detail="Rate metal does not match product")
        if rate.purity != payload.purity:
            raise HTTPException(status_code=422, detail="Rate purity does not match transaction purity")
        if rate_per_gram is not None and rate_per_gram != rate.rate_per_gram:
            raise HTTPException(status_code=422, detail="Rate conflicts with selected rate record")
        rate_per_gram = rate.rate_per_gram

    if rate_per_gram is None:
        rate = db.scalar(
            select(MetalRate)
            .where(
                MetalRate.metal == product.metal,
                MetalRate.purity == payload.purity,
                MetalRate.active.is_(True),
            )
            .order_by(MetalRate.verified_at.desc(), MetalRate.id.desc())
        )
        if rate is None:
            raise HTTPException(
                status_code=422,
                detail="No active verified rate for this metal and purity",
            )
        rate_per_gram = rate.rate_per_gram

    try:
        total = calculate_total(
            net_weight_grams=payload.net_weight_grams,
            rate_per_gram=rate_per_gram,
            charges=payload.charges,
            purity=payload.purity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if payload.amount_paid > total:
        raise HTTPException(
            status_code=422,
            detail="Amount paid cannot exceed transaction total",
        )

    if kind == "sale":
        available = get_stock_balance(db, payload.product_id, payload.location)
        if available < payload.net_weight_grams:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock at {payload.location}. Available: {available} grams",
            )

    reference = f"{'PUR' if kind == 'purchase' else 'SAL'}-{uuid4().hex[:12].upper()}"

    transaction = Transaction(
        reference=reference,
        kind=kind,
        product_id=payload.product_id,
        quantity_grams=payload.quantity_grams,
        gross_weight_grams=payload.gross_weight_grams,
        net_weight_grams=payload.net_weight_grams,
        deduction_grams=payload.deduction_grams,
        purity=payload.purity,
        rate_id=rate.id if rate else None,
        rate_per_gram=rate_per_gram,
        charges=payload.charges,
        total_amount=total,
        amount_paid=payload.amount_paid,
        party_name=payload.party_name,
        location=payload.location,
        destination=None,
        notes=payload.notes,
        created_by=payload.created_by,
    )

    try:
        db.add(transaction)
        db.flush()

        movement = StockMovement(
            transaction_id=transaction.id,
            product_id=payload.product_id,
            location=payload.location,
            quantity_delta_grams=(
                payload.net_weight_grams
                if kind == "purchase"
                else -payload.net_weight_grams
            ),
        )
        db.add(movement)

        # Record the initial payment in the payment ledger as well.
        if payload.amount_paid > 0:
            db.add(
                Payment(
                    transaction_id=transaction.id,
                    amount=payload.amount_paid,
                    method=payload.payment_method,
                    note="Initial payment at transaction creation",
                    recorded_by=payload.created_by,
                )
            )

        db.commit()
        db.refresh(transaction)
        return transaction
    except Exception:
        db.rollback()
        raise


def list_transactions(
    db: Session,
    kind: str | None = None,
) -> list[Transaction]:
    statement = select(Transaction).order_by(Transaction.created_at.desc())

    if kind is not None:
        if kind not in {"purchase", "sale"}:
            raise HTTPException(status_code=422, detail="Invalid transaction type")
        statement = statement.where(Transaction.kind == kind)

    return list(db.scalars(statement).all())
