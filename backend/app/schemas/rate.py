
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RateCreate(BaseModel):
    metal: Literal["gold", "silver"]
    purity: Decimal = Field(gt=0, le=100, max_digits=8, decimal_places=4)
    # Value entered for `unit`. The API converts it to a normalized
    # per-gram rate before storing it or using it in calculations.
    rate_per_gram: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    unit: Literal["gram", "tola", "kilogram"] = "gram"
    source_note: str = Field(default="", max_length=250)
    verified_by: str = Field(min_length=1, max_length=120)


class RateOut(BaseModel):
    id: int
    metal: str
    purity: Decimal
    # Normalized per-gram rate used by every calculation.
    rate_per_gram: Decimal
    # What the operator typed, in the unit they chose.
    unit: str
    entered_rate: Decimal
    source_note: str
    verified_by: str
    verified_at: datetime | None = None
    active: bool

    model_config = ConfigDict(from_attributes=True)
