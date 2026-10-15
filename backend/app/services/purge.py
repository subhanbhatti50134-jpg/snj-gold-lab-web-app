"""Permanent (hard) deletes for unreferenced records.

Cancelling a transaction is the reversible, audited path; purging is
the explicit manager/admin escape hatch the shop asked for. Every purge
keeps an audit_logs entry describing exactly what was removed.
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.party import Party
from app.models.payments import Payment
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.transaction import Transaction
from app.services.audit import log_audit
from app.services.inventory import get_stock_balance
from app.services.settings import get_bool_setting


def purge_transaction(db: Session, transaction_id: int, *, username: str) -> str:
    try:
        transaction = db.scalar(
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .with_for_update()
        )
        if transaction is None:
            raise HTTPException(status_code=404, detail="Transaction not found")

        if transaction.kind == "sale":
            active_return = db.scalar(
                select(Transaction.id)
                .where(
                    Transaction.kind == "sales_return",
                    Transaction.destination == transaction.reference,
                    Transaction.status == "active",
                )
                .limit(1)
            )
            if active_return is not None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This sale has sales returns against it. "
                        "Delete the returns first."
                    ),
                )

        movements = list(
            db.scalars(
                select(StockMovement).where(
                    StockMovement.transaction_id == transaction.id
                )
            ).all()
        )

        # Deleting the movement rows is mathematically identical to the
        # movement never having happened, so an active transaction whose
        # removal would drop stock below zero must be refused (mirrors
        # cancel_transaction). Cancelled rows already carry compensating
        # movements, so they net out and skip the guard.
        if transaction.status == "active" and not get_bool_setting(
            db, "allow_negative_stock"
        ):
            for movement in movements:
                balance = get_stock_balance(
                    db, movement.product_id, movement.location
                )
                projected = balance - movement.quantity_delta_grams
                if projected < 0:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Purge would create negative stock at "
                            f"{movement.location}: available "
                            f"{balance} grams"
                        ),
                    )

        payments = list(
            db.scalars(
                select(Payment).where(Payment.transaction_id == transaction.id)
            ).all()
        )
        for payment in payments:
            db.delete(payment)
        for movement in movements:
            db.delete(movement)

        detail = (
            f"{transaction.reference} ({transaction.kind}); "
            f"total {transaction.total_amount}; "
            f"status {transaction.status}; "
            f"movements {len(movements)}; payments {len(payments)}"
        )
        log_audit(
            db,
            username=username,
            action="transaction.delete",
            entity_type="transaction",
            entity_id=transaction.id,
            detail=detail,
        )
        db.delete(transaction)
        db.commit()
        return detail

    except Exception:
        db.rollback()
        raise


def purge_product(db: Session, product_id: int, *, username: str) -> str:
    try:
        product = db.scalar(
            select(Product).where(Product.id == product_id).with_for_update()
        )
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")

        used = db.scalar(
            select(Transaction.id)
            .where(Transaction.product_id == product.id)
            .limit(1)
        )
        if used is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Product has transaction history and cannot be deleted. "
                    "Deactivate it instead."
                ),
            )

        moved = db.scalar(
            select(StockMovement.id)
            .where(StockMovement.product_id == product.id)
            .limit(1)
        )
        if moved is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Product has stock history and cannot be deleted. "
                    "Deactivate it instead."
                ),
            )

        detail = f"{product.name} ({product.sku})"
        log_audit(
            db,
            username=username,
            action="product.delete",
            entity_type="product",
            entity_id=product.id,
            detail=detail,
        )
        db.delete(product)
        db.commit()
        return detail

    except Exception:
        db.rollback()
        raise


def purge_party(db: Session, party_id: int, *, username: str) -> str:
    try:
        party = db.scalar(
            select(Party).where(Party.id == party_id).with_for_update()
        )
        if party is None:
            raise HTTPException(status_code=404, detail="Party not found")

        used = db.scalar(
            select(Transaction.id)
            .where(Transaction.party_id == party.id)
            .limit(1)
        )
        if used is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Party has transaction history and cannot be deleted. "
                    "Deactivate it instead."
                ),
            )

        detail = f"{party.name} ({party.kind})"
        log_audit(
            db,
            username=username,
            action="party.delete",
            entity_type="party",
            entity_id=party.id,
            detail=detail,
        )
        db.delete(party)
        db.commit()
        return detail

    except Exception:
        db.rollback()
        raise
