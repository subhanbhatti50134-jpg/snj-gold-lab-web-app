from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OrderCreate(BaseModel):
    party_id: int | None = Field(default=None, gt=0)
    party_name: str = Field(default="", max_length=160)
    description: str = Field(min_length=1, max_length=300)
    estimated_weight_grams: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    agreed_rate_per_gram: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    advance_amount: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=16, decimal_places=2
    )
    due_date: date | None = Field(default=None)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_party(self):
        if self.party_id is None and not self.party_name.strip():
            raise ValueError(
                "Provide a saved party or a walk-in party name"
            )
        return self


class OrderUpdate(BaseModel):
    """Pending orders only; advances move through /advance."""

    description: str = Field(min_length=1, max_length=300)
    estimated_weight_grams: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    agreed_rate_per_gram: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    due_date: date | None = Field(default=None)
    notes: str = Field(default="", max_length=2000)


class OrderAdvance(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)


class OrderDeliver(BaseModel):
    product_id: int = Field(gt=0)
    # Defaults to the booked weight; override when the made item
    # weighs more or less than estimated.
    actual_weight_grams: Decimal | None = Field(
        default=None, gt=0, max_digits=16, decimal_places=4
    )
    location: str = Field(default="Main Store", min_length=1, max_length=100)


class OrderCancel(BaseModel):
    reason: str = Field(default="", max_length=500)


class OrderOut(BaseModel):
    id: int
    reference: str
    party_id: int | None = None
    party_name: str
    description: str
    estimated_weight_grams: Decimal
    agreed_rate_per_gram: Decimal
    estimated_total: Decimal
    advance_amount: Decimal
    balance: Decimal
    status: Literal["pending", "delivered", "cancelled"]
    due_date: date | None = None
    notes: str
    sale_id: int | None = None
    created_by: str
    created_at: datetime | None = None
    delivered_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
