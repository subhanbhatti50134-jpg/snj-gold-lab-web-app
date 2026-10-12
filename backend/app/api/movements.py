from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.session import get_db
from app.schemas.movements import (
    SalesReturnCreate,
    StockAdjustmentCreate,
)
from app.schemas.transaction import TransactionOut
from app.services.movements import (
    create_sales_return,
    create_stock_adjustment,
)

router = APIRouter(
    prefix="/api/movements",
    tags=["Sales Returns & Stock Adjustments"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "/sales-returns",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_sales_return(
    payload: SalesReturnCreate,
    db: Session = Depends(get_db),
):
    return create_sales_return(db, payload)


@router.post(
    "/adjustments",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_stock_adjustment(
    payload: StockAdjustmentCreate,
    db: Session = Depends(get_db),
):
    return create_stock_adjustment(db, payload)
