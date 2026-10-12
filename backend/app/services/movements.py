from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.transaction import Transaction
from app.schemas.movements import (
    SalesReturnCreate,
    StockAdjustmentCreate,
)
from app.services.inventory import get_stock_balance
from app.services.pricing import calculate_total


def create_sales_return(
    db: Session,
    payload: SalesReturnCreate,
) -> Transaction:
    original = db.scalar(
        select(Transaction)
        .where(Transaction.id == payload.original_sale_id)
        .with_for_update()
    )

    if original is None or original.kind != "sale":
        raise HTTPException(
            status_code=404,
            detail="Original sale transaction not found",
        )

    if not original.reference:
        raise HTTPException(
            status_code=409,
            detail="Original sale has no valid reference",
        )

    product = db.scalar(
        select(Product)
        .where(Product.id == original.product_id)
        .with_for_update()
    )

    if product is None:
        raise HTTPException(status_code=409, detail="Sale product not found")

    returned_before = db.scalar(
        select(
            func.coalesce(
                func.sum(Transaction.quantity_grams),
                Decimal("0"),
            )
        ).where(
            Transaction.kind == "sales_return",
            Transaction.destination == original.reference,
        )
    )
    returned_before = Decimal(str(returned_before or "0"))

    remaining_returnable = (
        Decimal(str(original.quantity_grams)) - returned_before
    )

    if payload.quantity_grams > remaining_returnable:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Return exceeds remaining sale quantity. "
                f"Remaining: {remaining_returnable} grams"
            ),
        )

    try:
        return_value = calculate_total(
            net_weight_grams=payload.quantity_grams,
            rate_per_gram=Decimal(str(original.rate_per_gram)),
            charges=Decimal("0"),
            purity=Decimal(str(original.purity)),
        )

        returned = Transaction(
            reference=f"RET-{uuid4().hex[:12].upper()}",
            kind="sales_return",
            product_id=original.product_id,
            quantity_grams=payload.quantity_grams,
            gross_weight_grams=payload.quantity_grams,
            net_weight_grams=payload.quantity_grams,
            deduction_grams=Decimal("0"),
            purity=original.purity,
            rate_id=original.rate_id,
            rate_per_gram=original.rate_per_gram,
            charges=Decimal("0"),
            total_amount=return_value,
            amount_paid=Decimal("0"),
            party_name=original.party_name,
            location=original.location,
            destination=original.reference,
            notes=payload.notes,
            created_by=payload.created_by,
        )

        db.add(returned)
        db.flush()

        db.add(
            StockMovement(
                transaction_id=returned.id,
                product_id=original.product_id,
                location=original.location,
                quantity_delta_grams=payload.quantity_grams,
            )
        )

        db.commit()
        db.refresh(returned)
        return returned

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def create_stock_adjustment(
    db: Session,
    payload: StockAdjustmentCreate,
) -> Transaction:
    product = db.scalar(
        select(Product)
        .where(Product.id == payload.product_id)
        .with_for_update()
    )

    if product is None or not product.active:
        raise HTTPException(
            status_code=404,
            detail="Active product not found",
        )

    if payload.direction == "decrease":
        available = get_stock_balance(
            db, payload.product_id, payload.location
        )

        if payload.quantity_grams > available:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Adjustment exceeds available stock. "
                    f"Available at {payload.location}: {available} grams"
                ),
            )

    delta = (
        payload.quantity_grams
        if payload.direction == "increase"
        else -payload.quantity_grams
    )

    try:
        adjustment = Transaction(
            reference=f"ADJ-{uuid4().hex[:12].upper()}",
            kind="stock_adjustment",
            product_id=product.id,
            quantity_grams=payload.quantity_grams,
            gross_weight_grams=payload.quantity_grams,
            net_weight_grams=payload.quantity_grams,
            deduction_grams=Decimal("0"),
            purity=product.purity,
            rate_id=None,
            rate_per_gram=Decimal("0"),
            charges=Decimal("0"),
            total_amount=Decimal("0"),
            amount_paid=Decimal("0"),
            party_name="",
            location=payload.location,
            destination=payload.direction,
            notes=payload.reason,
            created_by=payload.created_by,
        )

        db.add(adjustment)
        db.flush()

        db.add(
            StockMovement(
                transaction_id=adjustment.id,
                product_id=product.id,
                location=payload.location,
                quantity_delta_grams=delta,
            )
        )

        db.commit()
        db.refresh(adjustment)
        return adjustment

    except Exception:
        db.rollback()
        raise
