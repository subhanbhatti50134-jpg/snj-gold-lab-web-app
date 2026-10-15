from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.permissions import READ_ROLES, require_roles
from app.db.session import get_db
from app.models.party import Party
from app.models.payments import Payment
from app.models.transaction import Transaction

router = APIRouter(
    prefix="/api/reports",
    tags=["Financial Reports"],
)

ZERO = Decimal("0.00")


def apply_date_filter(query, column, date_from, date_to):
    """Filter on a plain-date column (transaction_date) inclusively."""
    if date_from is not None:
        query = query.filter(column >= date_from)
    if date_to is not None:
        query = query.filter(column <= date_to)
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
            query, Transaction.transaction_date, date_from, date_to
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
        query, Transaction.transaction_date, date_from, date_to
    )

    rows = (
        query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Resolve party phone numbers for WhatsApp reminders: linked party_id
    # first, then an exact unique name match (walk-in credit sales).
    party_ids = {t.party_id for t in rows if t.party_id is not None}
    party_names = {t.party_name for t in rows if t.party_name}
    by_id: dict[int, Party] = {}
    by_name: dict[str, Party] = {}
    if party_ids or party_names:
        parties = db.query(Party).filter(
            or_(Party.id.in_(party_ids), Party.name.in_(party_names))
        ).all()
        by_id = {p.id: p for p in parties}
        by_name = {p.name: p for p in parties}

    items = []
    for transaction in rows:
        total = Decimal(str(transaction.total_amount))
        paid = Decimal(str(transaction.amount_paid))
        party = by_id.get(transaction.party_id) or by_name.get(
            transaction.party_name
        )
        items.append({
            "transaction_id": transaction.id,
            "reference": transaction.reference,
            "kind": transaction.kind,
            "party_name": transaction.party_name,
            "party_id": transaction.party_id,
            "party_phone": party.phone if party else "",
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
        query, Transaction.transaction_date, date_from, date_to
    )

    transactions = query.order_by(
        Transaction.transaction_date.asc(), Transaction.id.asc()
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


@router.get(
    "/profit",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def profit_estimate(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Best-effort profit estimate from recorded purchase and sale totals.

    This is a simple sales-minus-purchases figure, NOT a precise
    cost-of-goods-sold calculation. It is labelled an estimate everywhere
    it is shown.
    """
    validate_dates(date_from, date_to)

    def total_for(kind: str) -> Decimal:
        query = db.query(
            func.coalesce(func.sum(Transaction.total_amount), 0)
        ).filter(
            Transaction.kind == kind,
            Transaction.status == "active",
        )
        query = apply_date_filter(
            query, Transaction.transaction_date, date_from, date_to
        )
        return Decimal(str(query.scalar()))

    sales = total_for("sale")
    purchases = total_for("purchase")
    returns_value = total_for("sales_return")
    estimated = sales - returns_value - purchases

    return {
        "sales_total": sales,
        "purchases_total": purchases,
        "sales_returns_value": returns_value,
        "estimated_profit": estimated,
        "is_estimate": True,
        "note": (
            "Best-effort estimate: sales minus returns minus purchases. "
            "Not a precise cost-of-goods-sold calculation."
        ),
    }
