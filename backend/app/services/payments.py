
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payments import Payment
from app.models.transaction import Transaction
from app.schemas.payments import PaymentCreate
from app.services.audit import log_audit


def record_payment(
    db: Session,
    transaction_id: int,
    payload: PaymentCreate,
    *,
    commit: bool = True,
) -> Payment:
    try:
        # Lock the transaction row so simultaneous payments cannot
        # both spend the same remaining balance.
        transaction = db.scalar(
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .with_for_update()
        )

        if transaction is None:
            raise HTTPException(status_code=404, detail="Transaction not found")

        if transaction.status != "active":
            raise HTTPException(
                status_code=409,
                detail="Payments cannot be recorded against a cancelled transaction",
            )

        remaining = transaction.total_amount - transaction.amount_paid

        if payload.amount > remaining:
            raise HTTPException(
                status_code=422,
                detail=f"Payment exceeds remaining due: {remaining}",
            )

        payment = Payment(
            transaction_id=transaction.id,
            amount=payload.amount,
            method=payload.method,
            note=payload.note,
            recorded_by=payload.recorded_by,
        )

        transaction.amount_paid += payload.amount
        db.add(payment)
        db.flush()

        log_audit(
            db,
            username=payload.recorded_by,
            action="payment.create",
            entity_type="payment",
            entity_id=payment.id,
            detail=(
                f"{payload.amount} ({payload.method}) against "
                f"{transaction.reference}"
            ),
        )

        if commit:
            db.commit()
            db.refresh(payment)

        return payment

    except Exception:
        db.rollback()
        raise


def list_payments(db: Session, transaction_id: int) -> list[Payment]:
    transaction = db.get(Transaction, transaction_id)

    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    statement = (
        select(Payment)
        .where(Payment.transaction_id == transaction_id)
        .order_by(Payment.paid_at.desc(), Payment.id.desc())
    )

    return list(db.scalars(statement).all())
