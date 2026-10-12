
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payments import Payment
from app.models.transaction import Transaction
from app.schemas.payments import PaymentCreate

def record_payment(
    db: Session,
    transaction_id: int,
    payload: PaymentCreate,
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
