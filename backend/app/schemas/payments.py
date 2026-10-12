
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    method: Literal["cash", "bank_transfer", "other"] = "cash"
    note: str = Field(default="", max_length=2000)
    recorded_by: str = Field(min_length=1, max_length=120)


class PaymentOut(BaseModel):
    id: int
    transaction_id: int
    amount: Decimal
    method: str
    note: str
    paid_at: datetime
    recorded_by: str

    model_config = ConfigDict(from_attributes=True)
