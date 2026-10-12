from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.session import get_db
from app.models.payments import Payment
from app.models.transaction import Transaction

router = APIRouter(
    prefix="/api/reports/cashflow",
    tags=["Cashflow Report"],
    dependencies=[Depends(require_api_key)],
)


def date_bounds(date_from: date | None, date_to: date | None):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from cannot be later than date_to",
        )

    start = datetime.combine(date_from, time.min) if date_from else None
    end = (
        datetime.combine(date_to + timedelta(days=1), time.min)
        if date_to else None
    )
    return start, end


@router.get("")
def cashflow_report(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    method: str | None = Query(None, min_length=1, max_length=30),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    start, end = date_bounds(date_from, date_to)

    query = (
        db.query(Payment, Transaction)
        .join(Transaction, Payment.transaction_id == Transaction.id)
        .filter(Transaction.kind.in_(("purchase", "sale")))
    )

    if start:
        query = query.filter(Payment.paid_at >= start)
    if end:
        query = query.filter(Payment.paid_at < end)
    if method:
        query = query.filter(Payment.method.ilike(method.strip()))

    # Calculate totals across the complete filtered date range,
    # before pagination.
    rows = query.order_by(Payment.paid_at.desc(), Payment.id.desc()).all()

    money_received = sum(
        (payment.amount for payment, transaction in rows
         if transaction.kind == "sale"),
        Decimal("0.00"),
    )
    money_paid = sum(
        (payment.amount for payment, transaction in rows
         if transaction.kind == "purchase"),
        Decimal("0.00"),
    )

    items = []
    for payment, transaction in rows[skip:skip + limit]:
        items.append({
            "payment_id": payment.id,
            "transaction_id": transaction.id,
            "reference": transaction.reference,
            "kind": transaction.kind,
            "party_name": transaction.party_name,
            "amount": payment.amount,
            "method": payment.method,
            "note": payment.note,
            "paid_at": payment.paid_at,
            "direction": (
                "received" if transaction.kind == "sale" else "paid"
            ),
        })

    return {
        "date_from": date_from,
        "date_to": date_to,
        "method": method,
        "money_received": money_received,
        "money_paid": money_paid,
        "net_cashflow": money_received - money_paid,
        "payment_count": len(rows),
        "items": items,
        "skip": skip,
        "limit": limit,
    }
