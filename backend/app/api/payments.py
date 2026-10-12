
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.session import get_db
from app.schemas.payments import PaymentCreate, PaymentOut
from app.services.payments import record_payment, list_payments

router = APIRouter(prefix="/api/transactions", tags=["Payments"])


@router.post(
    "/{transaction_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def add_payment(
    transaction_id: int,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
):
    return record_payment(db, transaction_id, payload)


@router.get("/{transaction_id}/payments", response_model=list[PaymentOut])
def get_transaction_payments(
    transaction_id: int,
    db: Session = Depends(get_db),
):
    return list_payments(db, transaction_id)
