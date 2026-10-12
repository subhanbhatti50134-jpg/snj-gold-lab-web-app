from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class SalesReturnCreate(BaseModel):
    original_sale_id: int = Field(gt=0)
    quantity_grams: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    created_by: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=2000)


class StockAdjustmentCreate(BaseModel):
    product_id: int = Field(gt=0)
    direction: Literal["increase", "decrease"]
    quantity_grams: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    location: str = Field(
        default="Main Store", min_length=1, max_length=100
    )
    reason: str = Field(min_length=1, max_length=500)
    created_by: str = Field(min_length=1, max_length=120)
