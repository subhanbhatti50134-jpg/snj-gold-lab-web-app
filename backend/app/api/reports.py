from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.permissions import READ_ROLES, require_roles
from app.db.session import get_db
from app.models.payments import Payment
from app.models.transaction import Transaction

router = APIRouter(
    prefix="/api/reports",
    tags=["Financial Reports"],
)

ZERO = Decimal("0.00")


def apply_date_filter(query, column, date_from, date_to):
    if date_from is not None:
        query = query.filter(
            column >= datetime.combine(date_from, time.min)
        )
    if date_to is not None:
        query = query.filter(
            column < datetime.combine(date_to + timedelta(days=1), time.min)
        )
    return query


def validate_dates(date_from, date_to):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from cannot be later than date_to",
        )


@router.get(
    "/summary",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def financial_summary(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    validate_dates(date_from, date_to)

    result = {}

    for kind in ("purchase", "sale"):
        query = db.query(
            func.coalesce(func.sum(Transaction.total_amount), 0),
            func.coalesce(func.sum(Transaction.amount_paid), 0),
        ).filter(
            Transaction.kind == kind,
            Transaction.status == "active",
        )

        query = apply_date_filter(
            query, Transaction.created_at, date_from, date_to
        )

        total, paid = query.one()
        total = Decimal(str(total))
        paid = Decimal(str(paid))

        result[kind] = {
            "total_amount": total,
            "amount_paid": paid,
            "remaining_amount": total - paid,
        }

    result["sales_returns"] = {
        "count": db.query(Transaction).filter(
            Transaction.kind == "sales_return",
            Transaction.status == "active",
        ).count()
    }

    result["stock_adjustments"] = {
        "count": db.query(Transaction).filter(
            Transaction.kind == "stock_adjustment",
            Transaction.status == "active",
        ).count()
    }

    return result


@router.get(
    "/outstanding",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def outstanding_report(
    kind: str | None = Query(default=None, pattern="^(purchase|sale)$"),
    party_name: str | None = Query(default=None, max_length=160),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    validate_dates(date_from, date_to)

    query = db.query(Transaction).filter(
        Transaction.kind.in_(("purchase", "sale")),
        Transaction.status == "active",
        Transaction.total_amount > Transaction.amount_paid,
    )

    if kind:
        query = query.filter(Transaction.kind == kind)

    if party_name:
        query = query.filter(
            Transaction.party_name.ilike(f"%{party_name.strip()}%")
        )

    query = apply_date_filter(
        query, Transaction.created_at, date_from, date_to
    )

    rows = (
        query.order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = []
    for transaction in rows:
        total = Decimal(str(transaction.total_amount))
        paid = Decimal(str(transaction.amount_paid))
        items.append({
            "transaction_id": transaction.id,
            "reference": transaction.reference,
            "kind": transaction.kind,
            "party_name": transaction.party_name,
            "created_at": transaction.created_at,
            "total_amount": total,
            "amount_paid": paid,
            "remaining_amount": total - paid,
            "location": transaction.location,
        })

    return {
        "items": items,
        "count": len(items),
        "skip": skip,
        "limit": limit,
    }


@router.get(
    "/party-ledger",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def party_ledger(
    party_name: str = Query(min_length=1, max_length=160),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    validate_dates(date_from, date_to)

    query = db.query(Transaction).filter(
        Transaction.party_name.ilike(party_name.strip()),
        Transaction.kind.in_(("purchase", "sale", "sales_return")),
        Transaction.status == "active",
    )

    query = apply_date_filter(
        query, Transaction.created_at, date_from, date_to
    )

    transactions = query.order_by(
        Transaction.created_at.asc(), Transaction.id.asc()
    ).all()

    ledger = []
    for transaction in transactions:
        payments = (
            db.query(Payment)
            .filter(Payment.transaction_id == transaction.id)
            .order_by(Payment.paid_at.asc(), Payment.id.asc())
            .all()
        )

        total = Decimal(str(transaction.total_amount))
        paid = Decimal(str(transaction.amount_paid))

        ledger.append({
            "transaction_id": transaction.id,
            "reference": transaction.reference,
            "kind": transaction.kind,
            "created_at": transaction.created_at,
            "quantity_grams": transaction.quantity_grams,
            "total_amount": total,
            "amount_paid": paid,
            "remaining_amount": total - paid,
            "payments": [
                {
                    "id": payment.id,
                    "amount": payment.amount,
                    "method": payment.method,
                    "note": payment.note,
                    "paid_at": payment.paid_at,
                }
                for payment in payments
            ],
        })

    return {
        "party_name": party_name.strip(),
        "transactions": ledger,
        "transaction_count": len(ledger),
    }
