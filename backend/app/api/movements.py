from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.permissions import MANAGE_ROLES, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.movements import (
    SalesReturnCreate,
    StockAdjustmentCreate,
    StockTransferCreate,
)
from app.schemas.transaction import TransactionOut
from app.services.movements import (
    create_sales_return,
    create_stock_adjustment,
    create_stock_transfer,
)

router = APIRouter(
    prefix="/api/movements",
    tags=["Returns, Adjustments & Transfers"],
)


@router.post(
    "/sales-returns",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_sales_return(
    payload: SalesReturnCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    # The audit name comes from the logged-in user, never from the client.
    payload = payload.model_copy(update={"created_by": user.username})
    return create_sales_return(db, payload)


@router.post(
    "/adjustments",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_stock_adjustment(
    payload: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    payload = payload.model_copy(update={"created_by": user.username})
    return create_stock_adjustment(db, payload)


@router.post(
    "/transfers",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_stock_transfer(
    payload: StockTransferCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE_ROLES)),
):
    payload = payload.model_copy(update={"created_by": user.username})
    return create_stock_transfer(db, payload)
