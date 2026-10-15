from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import (
    MANAGE_ROLES,
    OPERATE_ROLES,
    READ_ROLES,
    require_roles,
)
from app.db.session import get_db
from app.models.order import LayawayOrder
from app.models.user import User
from app.schemas.order import (
    OrderAdvance,
    OrderCancel,
    OrderCreate,
    OrderDeliver,
    OrderOut,
    OrderUpdate,
)
from app.schemas.transaction import TransactionOut
from app.services import idempotency
from app.services.orders import (
    add_advance,
    cancel_order,
    create_order,
    deliver_order,
    update_order,
)

router = APIRouter(prefix="/api/orders", tags=["Bayana Orders"])


@router.post(
    "",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*OPERATE_ROLES))],
)
def add_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATE_ROLES)),
    idem_key: str | None = Depends(idempotency.idempotency_key_header),
):
    replay = idempotency.begin(
        db,
        key=idem_key,
        user_id=user.id,
        endpoint="POST /api/orders",
        payload=payload,
    )
    if replay is not None:
        return JSONResponse(
            status_code=replay.status_code,
            content=jsonable_encoder(replay.body),
        )

    order = create_order(db, payload, user.username)
    idempotency.record(
        db,
        key=idem_key,
        status_code=status.HTTP_201_CREATED,
        body=OrderOut.model_validate(order),
    )
    db.commit()
    db.refresh(order)
    return order


@router.get(
    "",
    response_model=list[OrderOut],
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def list_orders(
    order_status: str | None = Query(
        default=None, alias="status", pattern="^(pending|delivered|cancelled)$"
    ),
    search: str | None = Query(default=None, min_length=1, max_length=160),
    db: Session = Depends(get_db),
):
    query = db.query(LayawayOrder)

    if order_status:
        query = query.filter(LayawayOrder.status == order_status)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                LayawayOrder.party_name.ilike(term),
                LayawayOrder.description.ilike(term),
                LayawayOrder.reference.ilike(term),
            )
        )

    return query.order_by(
        (LayawayOrder.status == "pending").desc(),
        LayawayOrder.created_at.desc(),
    ).all()


@router.get(
    "/{order_id}",
    response_model=OrderOut,
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
):
    order = db.get(LayawayOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch(
    "/{order_id}",
    response_model=OrderOut,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
def edit_order(
    order_id: int,
    payload: OrderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    order = db.scalar(
        select(LayawayOrder)
        .where(LayawayOrder.id == order_id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    update_order(db, order, payload, user.username)
    db.commit()
    db.refresh(order)
    return order


@router.post(
    "/{order_id}/advance",
    response_model=OrderOut,
    dependencies=[Depends(require_roles(*OPERATE_ROLES))],
)
def record_advance(
    order_id: int,
    payload: OrderAdvance,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATE_ROLES)),
    idem_key: str | None = Depends(idempotency.idempotency_key_header),
):
    replay = idempotency.begin(
        db,
        key=idem_key,
        user_id=user.id,
        endpoint=f"POST /api/orders/{order_id}/advance",
        payload=payload,
    )
    if replay is not None:
        return JSONResponse(
            status_code=replay.status_code,
            content=jsonable_encoder(replay.body),
        )

    order = db.scalar(
        select(LayawayOrder)
        .where(LayawayOrder.id == order_id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    add_advance(db, order, payload.amount, user.username)
    idempotency.record(
        db,
        key=idem_key,
        status_code=status.HTTP_200_OK,
        body=OrderOut.model_validate(order),
    )
    db.commit()
    db.refresh(order)
    return order


@router.post(
    "/{order_id}/deliver",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*OPERATE_ROLES))],
)
def deliver(
    order_id: int,
    payload: OrderDeliver,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATE_ROLES)),
    idem_key: str | None = Depends(idempotency.idempotency_key_header),
):
    replay = idempotency.begin(
        db,
        key=idem_key,
        user_id=user.id,
        endpoint=f"POST /api/orders/{order_id}/deliver",
        payload=payload,
    )
    if replay is not None:
        return JSONResponse(
            status_code=replay.status_code,
            content=jsonable_encoder(replay.body),
        )

    order = db.scalar(
        select(LayawayOrder)
        .where(LayawayOrder.id == order_id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    _, sale = deliver_order(db, order, payload, user.username)
    idempotency.record(
        db,
        key=idem_key,
        status_code=status.HTTP_201_CREATED,
        body=TransactionOut.model_validate(sale),
    )
    db.commit()
    db.refresh(sale)
    return sale


@router.post(
    "/{order_id}/cancel",
    response_model=OrderOut,
    dependencies=[Depends(require_roles(*MANAGE_ROLES))],
)
def cancel(
    order_id: int,
    payload: OrderCancel,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    order = db.scalar(
        select(LayawayOrder)
        .where(LayawayOrder.id == order_id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    cancel_order(db, order, payload.reason, user.username)
    db.commit()
    db.refresh(order)
    return order
