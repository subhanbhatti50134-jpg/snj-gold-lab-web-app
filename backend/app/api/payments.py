from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.permissions import OPERATE_ROLES, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.payments import PaymentCreate, PaymentOut
from app.services import idempotency
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
    idem_key: str | None = Depends(idempotency.idempotency_key_header),
):
    # The audit name comes from the logged-in user, never from the client.
    # A duplicate Idempotency-Key replays the first response instead of
    # recording the payment twice.
    replay = idempotency.begin(
        db,
        key=idem_key,
        user_id=user.id,
        endpoint=f"POST /api/transactions/{transaction_id}/payments",
        payload=payload,
    )
    if replay is not None:
        return JSONResponse(
            status_code=replay.status_code, content=jsonable_encoder(replay.body)
        )

    payload = payload.model_copy(update={"recorded_by": user.username})
    result = record_payment(db, transaction_id, payload, commit=False)
    idempotency.record(
        db,
        key=idem_key,
        status_code=status.HTTP_201_CREATED,
        body=PaymentOut.model_validate(result),
    )
    db.commit()
    db.refresh(result)
    return result


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
