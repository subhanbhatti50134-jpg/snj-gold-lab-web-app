from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payments import Payment
from app.models.stock_movement import StockMovement
from app.models.transaction import Transaction
from app.services.audit import log_audit
from app.services.inventory import get_stock_balance
from app.services.settings import get_bool_setting

REFUND_METHOD = "other"


def cancel_transaction(
    db: Session,
    transaction_id: int,
    *,
    reason: str,
    username: str,
    include_payments: bool = False,
) -> Transaction:
    """Cancel a transaction without destroying its history.

    The original row stays exactly as it was recorded; cancellation
    adds compensating stock movements (and, when requested, refund
    payment entries) and marks the transaction as cancelled so every
    report keeps an auditable trail.
    """
    try:
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
                detail="Transaction is already cancelled",
            )

        if transaction.kind == "sale":
            active_returns = db.scalar(
                select(Transaction.id)
                .where(
                    Transaction.kind == "sales_return",
                    Transaction.destination == transaction.reference,
                    Transaction.status == "active",
                )
                .limit(1)
            )
            if active_returns is not None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This sale has sales returns against it. "
                        "Cancel the returns first."
                    ),
                )

        movements = list(
            db.scalars(
                select(StockMovement).where(
                    StockMovement.transaction_id == transaction.id
                )
            ).all()
        )

        allow_negative = get_bool_setting(db, "allow_negative_stock")

        # Reverse every stock effect of this transaction and refuse the
        # cancellation if it would leave a negative balance.
        for movement in movements:
            opposite = -movement.quantity_delta_grams

            if not allow_negative:
                projected = get_stock_balance(
                    db, movement.product_id, movement.location
                ) + opposite
                if projected < 0:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Cancellation would create negative stock at "
                            f"{movement.location}: available "
                            f"{get_stock_balance(db, movement.product_id, movement.location)} grams"
                        ),
                    )

            db.add(
                StockMovement(
                    transaction_id=transaction.id,
                    product_id=movement.product_id,
                    location=movement.location,
                    quantity_delta_grams=opposite,
                )
            )

        paid = Decimal(str(transaction.amount_paid))

        if paid > 0:
            if not include_payments:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"This transaction has recorded payments of {paid}. "
                        "Resubmit with include_payments=true to post "
                        "refund entries for them."
                    ),
                )

            db.add(
                Payment(
                    transaction_id=transaction.id,
                    amount=-paid,
                    method=REFUND_METHOD,
                    note=(
                        f"Refund posted while cancelling "
                        f"{transaction.reference}"
                    ),
                    recorded_by=username,
                )
            )
            transaction.amount_paid = Decimal("0.00")

        transaction.status = "cancelled"
        transaction.cancelled_at = datetime.now(UTC)
        transaction.cancelled_by = username
        transaction.cancel_reason = reason

        log_audit(
            db,
            username=username,
            action="transaction.cancel",
            entity_type="transaction",
            entity_id=transaction.id,
            detail=(
                f"{transaction.reference} ({transaction.kind}); "
                f"reason: {reason}; refunds: {include_payments}"
            ),
        )

        db.commit()
        db.refresh(transaction)
        return transaction

    except Exception:
        db.rollback()
        raise
