
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.stock_movement import StockMovement


def get_stock_balance(
    db: Session,
    product_id: int,
    location: str | None = None,
) -> Decimal:
    """Return the net stock balance in grams."""
    statement = select(
        func.coalesce(
            func.sum(StockMovement.quantity_delta_grams),
            Decimal("0"),
        )
    ).where(StockMovement.product_id == product_id)

    if location is not None:
        statement = statement.where(StockMovement.location == location)

    balance = db.scalar(statement)
    return Decimal(str(balance or "0"))


def get_inventory(
    db: Session,
    location: str | None = None,
) -> list[dict]:
    """Return stock balances grouped by product and location."""
    statement = (
        select(
            StockMovement.product_id,
            StockMovement.location,
            func.sum(StockMovement.quantity_delta_grams).label("balance_grams"),
        )
        .group_by(
            StockMovement.product_id,
            StockMovement.location,
        )
        .having(
            func.sum(StockMovement.quantity_delta_grams) != 0
        )
        .order_by(
            StockMovement.product_id,
            StockMovement.location,
        )
    )

    if location is not None:
        statement = statement.where(StockMovement.location == location)

    rows = db.execute(statement).all()

    return [
        {
            "product_id": row.product_id,
            "location": row.location,
            "balance_grams": Decimal(str(row.balance_grams)),
        }
        for row in rows
    ]
