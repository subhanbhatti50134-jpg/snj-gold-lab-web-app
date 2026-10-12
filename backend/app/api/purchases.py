
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.session import get_db
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services.transactions import create_transaction, list_transactions

router = APIRouter(prefix="/api/purchases", tags=["Purchases"])


@router.post(
    "",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_purchase(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
):
    return create_transaction(db, payload, "purchase")


@router.get("", response_model=list[TransactionOut])
def get_purchases(db: Session = Depends(get_db)):
    return list_transactions(db, "purchase")
