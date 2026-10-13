from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.permissions import OPERATE_ROLES, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.transaction import (
    SaleBatchCreate,
    TransactionCreate,
    TransactionOut,
)
from app.services import idempotency
from app.services.transactions import create_transaction, list_transactions

router = APIRouter(prefix="/api/sales", tags=["Sales"])


@router.post(
    "",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_sale(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATE_ROLES)),
    idem_key: str | None = Depends(idempotency.idempotency_key_header),
):
    # A duplicate key replays the first response instead of selling twice.
    replay = idempotency.begin(
        db,
        key=idem_key,
        user_id=user.id,
        endpoint="POST /api/sales",
        payload=payload,
    )
    if replay is not None:
        return JSONResponse(
            status_code=replay.status_code, content=jsonable_encoder(replay.body)
        )

    payload = payload.model_copy(update={"created_by": user.username})
    result = create_transaction(db, payload, "sale", commit=False)
    idempotency.record(
        db,
        key=idem_key,
        status_code=status.HTTP_201_CREATED,
        body=TransactionOut.model_validate(result),
    )
    db.commit()
    db.refresh(result)
    return result


@router.post(
    "/batch",
    response_model=list[TransactionOut],
    status_code=status.HTTP_201_CREATED,
)
def create_sales_batch(
    payload: SaleBatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATE_ROLES)),
    idem_key: str | None = Depends(idempotency.idempotency_key_header),
):
    """POS checkout: create several sales atomically.

    Either every item in the batch is saved or none of them are, so a
    failed line can never leave a half-completed sale behind. An
    Idempotency-Key makes a retried checkout return the original sales
    instead of recording them twice.
    """
    replay = idempotency.begin(
        db,
        key=idem_key,
        user_id=user.id,
        endpoint="POST /api/sales/batch",
        payload=payload,
    )
    if replay is not None:
        return JSONResponse(
            status_code=replay.status_code, content=jsonable_encoder(replay.body)
        )

    results = []
    try:
        for item in payload.items:
            item = item.model_copy(update={"created_by": user.username})
            results.append(
                create_transaction(db, item, "sale", commit=False)
            )
        idempotency.record(
            db,
            key=idem_key,
            status_code=status.HTTP_201_CREATED,
            body=[TransactionOut.model_validate(t) for t in results],
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Checkout failed, no sales were recorded: {exc}",
        ) from exc

    for transaction in results:
        db.refresh(transaction)
    return results


@router.get(
    "",
    response_model=list[TransactionOut],
    dependencies=[Depends(require_roles(*OPERATE_ROLES))],
)
def get_sales(db: Session = Depends(get_db)):
    return list_transactions(db, "sale")
