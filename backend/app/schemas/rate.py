
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RateCreate(BaseModel):
    metal: Literal["gold", "silver"]
    purity: Decimal = Field(gt=0, le=100, max_digits=8, decimal_places=4)
    rate_per_gram: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    source_note: str = Field(default="", max_length=250)
    verified_by: str = Field(min_length=1, max_length=120)


class RateOut(RateCreate):
    id: int
    active: bool

    model_config = ConfigDict(from_attributes=True)
