from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.permissions import OPERATE_ROLES, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services.transactions import create_transaction, list_transactions

router = APIRouter(prefix="/api/purchases", tags=["Purchases"])


@router.post(
    "",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATE_ROLES)),
):
    # The audit name comes from the logged-in user, never from the client.
    payload = payload.model_copy(update={"created_by": user.username})
    return create_transaction(db, payload, "purchase")


@router.get(
    "",
    response_model=list[TransactionOut],
    dependencies=[Depends(require_roles(*OPERATE_ROLES))],
)
def get_purchases(db: Session = Depends(get_db)):
    return list_transactions(db, "purchase")
