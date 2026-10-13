from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.permissions import MANAGE_ROLES, READ_ROLES, require_roles
from app.db.session import get_db
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.movements import TransactionCancel
from app.schemas.transaction import TransactionOut
from app.services.reversals import cancel_transaction

router = APIRouter(
    prefix="/api/transactions",
    tags=["Transaction History"],
)

TransactionKind = Literal[
    "purchase",
    "sale",
    "sales_return",
    "stock_adjustment",
    "stock_transfer",
]


@router.get(
    "",
    response_model=list[TransactionOut],
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_transactions(
    kind: TransactionKind | None = Query(default=None),
    status: Literal["active", "cancelled", "all"] = Query(default="active"),
    search: str | None = Query(default=None, min_length=1, max_length=160),
    product_id: int | None = Query(default=None, gt=0),
    location: str | None = Query(default=None, min_length=1, max_length=100),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from cannot be later than date_to",
        )

    query = db.query(Transaction)

    if search:
        term = f"%{search.strip()}%"
        query = query.join(Product, Product.id == Transaction.product_id).filter(
            (Transaction.reference.ilike(term))
            | (Transaction.party_name.ilike(term))
            | (Product.name.ilike(term))
            | (Product.sku.ilike(term))
        )

    if kind is not None:
        query = query.filter(Transaction.kind == kind)

    if status != "all":
        query = query.filter(Transaction.status == status)

    if product_id is not None:
        query = query.filter(Transaction.product_id == product_id)

    if location is not None:
        query = query.filter(Transaction.location == location.strip())

    if date_from is not None:
        query = query.filter(
            Transaction.created_at >= datetime.combine(date_from, time.min)
        )

    if date_to is not None:
        query = query.filter(
            Transaction.created_at < datetime.combine(
                date_to + timedelta(days=1), time.min
            )
        )

    return (
        query.order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post(
    "/{transaction_id}/cancel",
    response_model=TransactionOut,
)
def cancel(
    transaction_id: int,
    payload: TransactionCancel,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    """Cancel a transaction using reversal entries, never deletion."""
    return cancel_transaction(
        db,
        transaction_id,
        reason=payload.reason,
        username=user.username,
        include_payments=payload.include_payments,
    )
