from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SalesReturnCreate(BaseModel):
    original_sale_id: int = Field(gt=0)
    quantity_grams: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    created_by: str = Field(default="", max_length=120)
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
    created_by: str = Field(default="", max_length=120)


class StockTransferCreate(BaseModel):
    """Move stock between locations without changing the total."""

    product_id: int = Field(gt=0)
    quantity_grams: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    from_location: str = Field(min_length=1, max_length=100)
    to_location: str = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=2000)
    created_by: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def validate_locations(self):
        if self.from_location.strip() == self.to_location.strip():
            raise ValueError(
                "from_location and to_location must be different"
            )
        return self


class TransactionCancel(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    include_payments: bool = False
