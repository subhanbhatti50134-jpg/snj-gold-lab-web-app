from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.permissions import OPERATE_ROLES, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.payments import PaymentCreate, PaymentOut
from app.services.payments import record_payment, list_payments

router = APIRouter(prefix="/api/transactions", tags=["Payments"])


@router.post(
    "/{transaction_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_payment(
    transaction_id: int,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATE_ROLES)),
):
    # The audit name comes from the logged-in user, never from the client.
    payload = payload.model_copy(update={"recorded_by": user.username})
    return record_payment(db, transaction_id, payload)


@router.get(
    "/{transaction_id}/payments",
    response_model=list[PaymentOut],
    dependencies=[Depends(require_roles(*OPERATE_ROLES))],
)
def get_transaction_payments(
    transaction_id: int,
    db: Session = Depends(get_db),
):
    return list_payments(db, transaction_id)
