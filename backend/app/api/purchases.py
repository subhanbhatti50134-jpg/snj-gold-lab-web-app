from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.permissions import OPERATE_ROLES, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services import idempotency
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
    idem_key: str | None = Depends(idempotency.idempotency_key_header),
):
    # The audit name comes from the logged-in user, never from the client.
    # A duplicate Idempotency-Key replays the first response instead of
    # recording the purchase twice.
    replay = idempotency.begin(
        db,
        key=idem_key,
        user_id=user.id,
        endpoint="POST /api/purchases",
        payload=payload,
    )
    if replay is not None:
        return JSONResponse(
            status_code=replay.status_code, content=jsonable_encoder(replay.body)
        )

    payload = payload.model_copy(update={"created_by": user.username})
    result = create_transaction(db, payload, "purchase", commit=False)
    idempotency.record(
        db,
        key=idem_key,
        status_code=status.HTTP_201_CREATED,
        body=TransactionOut.model_validate(result),
    )
    db.commit()
    db.refresh(result)
    return result


@router.get(
    "",
    response_model=list[TransactionOut],
    dependencies=[Depends(require_roles(*OPERATE_ROLES))],
)
def get_purchases(db: Session = Depends(get_db)):
    return list_transactions(db, "purchase")
