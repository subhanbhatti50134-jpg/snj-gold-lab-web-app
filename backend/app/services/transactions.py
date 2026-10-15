
from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.metal_rate import MetalRate
from app.models.party import Party
from app.models.payments import Payment
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate
from app.services.audit import log_audit
from app.services.inventory import get_stock_balance
from app.services.pricing import calculate_making, calculate_total, normalize_rate
from app.services.settings import get_bool_setting


def _resolve_party(
    db: Session, payload: TransactionCreate
) -> tuple[int | None, str]:
    """Prefer the linked party record; its name is the server's copy."""
    if payload.party_id is None:
        return None, payload.party_name.strip()

    party = db.get(Party, payload.party_id)

    if party is None or not party.active:
        raise HTTPException(status_code=404, detail="Active party not found")

    return party.id, party.name


def create_transaction(
    db: Session,
    payload: TransactionCreate,
    kind: str,
    *,
    commit: bool = True,
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

    party_id, party_name = _resolve_party(db, payload)

    rate = None
    # Normalize the client-entered rate to grams first so the value is
    # comparable with the stored per-gram rate.
    rate_per_gram = (
        normalize_rate(payload.rate_per_gram, payload.rate_unit)
        if payload.rate_per_gram is not None
        else None
    )

    if payload.rate_id is not None:
        rate = db.get(MetalRate, payload.rate_id)
        if rate is None or not rate.active:
            raise HTTPException(status_code=422, detail="Active metal rate not found")
        if rate.metal != product.metal:
            raise HTTPException(status_code=422, detail="Rate metal does not match product")
        if rate.purity != payload.purity:
            raise HTTPException(
                status_code=422,
                detail="Rate purity does not match transaction purity",
            )
        if rate_per_gram is not None and rate_per_gram != rate.rate_per_gram:
            raise HTTPException(
                status_code=422,
                detail="Rate conflicts with selected rate record",
            )
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

    making = Decimal("0")
    if payload.making_charge_type or payload.making_charge_value != 0:
        if kind != "sale":
            raise HTTPException(
                status_code=422,
                detail="Making charge applies to sales only",
            )
        try:
            making = calculate_making(
                net_weight_grams=payload.net_weight_grams,
                rate_per_gram=rate_per_gram,
                purity=payload.purity,
                charge_type=payload.making_charge_type,
                charge_value=payload.making_charge_value,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        total = calculate_total(
            net_weight_grams=payload.net_weight_grams,
            rate_per_gram=rate_per_gram,
            charges=payload.charges,
            purity=payload.purity,
            making=making,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if payload.amount_paid > total:
        raise HTTPException(
            status_code=422,
            detail="Amount paid cannot exceed transaction total",
        )

    allow_negative = get_bool_setting(db, "allow_negative_stock")

    if kind == "sale" and not allow_negative:
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
        party_id=party_id,
        quantity_grams=payload.quantity_grams,
        gross_weight_grams=payload.gross_weight_grams,
        net_weight_grams=payload.net_weight_grams,
        deduction_grams=payload.deduction_grams,
        purity=payload.purity,
        rate_id=rate.id if rate else None,
        rate_per_gram=rate_per_gram,
        charges=payload.charges,
        making_charge_type=payload.making_charge_type,
        making_charge_value=payload.making_charge_value,
        making_amount=making,
        total_amount=total,
        amount_paid=payload.amount_paid,
        party_name=party_name,
        location=payload.location,
        destination=None,
        notes=payload.notes,
        created_by=payload.created_by,
        transaction_date=payload.transaction_date or date.today(),
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

        log_audit(
            db,
            username=payload.created_by,
            action=f"{kind}.create",
            entity_type="transaction",
            entity_id=transaction.id,
            detail=(
                f"{reference}; {payload.net_weight_grams}g; "
                f"total {total}; party {party_name or 'n/a'}"
            ),
        )

        if commit:
            db.commit()
            db.refresh(transaction)
        return transaction
    except Exception:
        db.rollback()
        raise


def list_transactions(
    db: Session,
    kind: str | None = None,
    include_cancelled: bool = False,
) -> list[Transaction]:
    statement = select(Transaction)

    if kind is not None:
        if kind not in {"purchase", "sale"}:
            raise HTTPException(status_code=422, detail="Invalid transaction type")
        statement = statement.where(Transaction.kind == kind)

    if not include_cancelled:
        statement = statement.where(Transaction.status == "active")

    statement = statement.order_by(Transaction.created_at.desc())
    return list(db.scalars(statement).all())
