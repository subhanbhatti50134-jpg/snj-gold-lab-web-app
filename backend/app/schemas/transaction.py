
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TransactionCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity_grams: Decimal = Field(gt=0, max_digits=16, decimal_places=4)
    gross_weight_grams: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    net_weight_grams: Decimal = Field(
        gt=0, max_digits=16, decimal_places=4
    )
    deduction_grams: Decimal = Field(
        ge=0, max_digits=16, decimal_places=4
    )
    purity: Decimal = Field(ge=0, le=100, max_digits=8, decimal_places=4)

    rate_id: int | None = Field(default=None, gt=0)
    rate_per_gram: Decimal | None = Field(default=None, gt=0)
    charges: Decimal = Field(default=Decimal("0"), ge=0)
    amount_paid: Decimal = Field(default=Decimal("0"), ge=0)
    payment_method: Literal["cash", "bank_transfer", "other"] = "cash"

    party_name: str = Field(default="", max_length=160)
    location: str = Field(default="Main Store", min_length=1, max_length=100)
    destination: str | None = Field(default=None, max_length=100)
    notes: str = Field(default="", max_length=2000)
    created_by: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_weights(self):
        if self.net_weight_grams + self.deduction_grams > self.gross_weight_grams:
            raise ValueError(
                "Net weight plus deductions cannot exceed gross weight"
            )

        if self.quantity_grams != self.net_weight_grams:
            raise ValueError("Quantity must equal net weight")

        if self.amount_paid < 0 or self.charges < 0:
            raise ValueError("Payment and charges cannot be negative")

        return self


class TransactionOut(BaseModel):
    id: int
    reference: str
    kind: str
    product_id: int
    quantity_grams: Decimal
    rate_per_gram: Decimal
    charges: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    party_name: str
    location: str
    destination: str | None
    created_by: str

    model_config = ConfigDict(from_attributes=True)
