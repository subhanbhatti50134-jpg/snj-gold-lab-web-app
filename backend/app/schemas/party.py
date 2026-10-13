from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PartyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    kind: Literal["customer", "supplier", "both"] = "customer"
    phone: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=255)
    notes: str = Field(default="", max_length=2000)


class PartyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    kind: Literal["customer", "supplier", "both"] | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)
    active: bool | None = None


class PartyOut(BaseModel):
    id: int
    name: str
    kind: str
    phone: str
    address: str
    notes: str
    active: bool
    created_at: datetime
    receivable: Decimal
    payable: Decimal
    net: Decimal

    model_config = ConfigDict(from_attributes=True)
