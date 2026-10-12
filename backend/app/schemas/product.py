
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)
    category: Literal[
        "loose_metal", "biscuit", "jewellery", "laboratory_material"
    ]
    metal: Literal["gold", "silver", "other"]
    purity: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class ProductOut(ProductCreate):
    id: int
    active: bool

    model_config = ConfigDict(from_attributes=True)
