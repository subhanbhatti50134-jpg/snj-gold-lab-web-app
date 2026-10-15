from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RateUnit = Literal["gram", "tola", "kilogram"]
MakingChargeType = Literal["", "per_gram", "percent", "fixed"]


class TransactionCreate(BaseModel):
    product_id: int = Field(gt=0)
    party_id: int | None = Field(default=None, gt=0)
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
    # rate_per_gram is expressed per rate_unit; the service normalizes
    # it to a per-gram rate before any calculation.
    rate_per_gram: Decimal | None = Field(default=None, gt=0)
    rate_unit: RateUnit = "gram"
    charges: Decimal = Field(default=Decimal("0"), ge=0)
    # Ujra: per_gram = value per gram of net weight, percent = percent of
    # metal value, fixed = flat amount. Empty type means no making charge.
    making_charge_type: MakingChargeType = ""
    making_charge_value: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=16, decimal_places=4
    )
    amount_paid: Decimal = Field(default=Decimal("0"), ge=0)
    payment_method: Literal["cash", "bank_transfer", "other"] = "cash"

    party_name: str = Field(default="", max_length=160)
    location: str = Field(default="Main Store", min_length=1, max_length=100)
    destination: str | None = Field(default=None, max_length=100)
    notes: str = Field(default="", max_length=2000)
    created_by: str = Field(default="", max_length=120)
    # Business date of the transaction; defaults to today server-side.
    transaction_date: date | None = Field(default=None)

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

    @model_validator(mode="after")
    def validate_making_charge(self):
        if self.making_charge_type:
            if self.making_charge_value <= 0:
                raise ValueError(
                    "Making charge value must be greater than zero"
                )
        elif self.making_charge_value != 0:
            raise ValueError(
                "Select a making charge type or set the value to zero"
            )

        return self


class TransactionOut(BaseModel):
    id: int
    reference: str
    kind: str
    status: str
    product_id: int
    party_id: int | None = None
    quantity_grams: Decimal
    rate_per_gram: Decimal
    charges: Decimal
    making_charge_type: str = ""
    making_charge_value: Decimal = Decimal("0")
    making_amount: Decimal = Decimal("0")
    total_amount: Decimal
    amount_paid: Decimal
    party_name: str
    location: str
    destination: str | None
    created_by: str
    cancelled_by: str | None = None
    cancel_reason: str | None = None
    created_at: datetime | None = None
    transaction_date: date | None = None

    model_config = ConfigDict(from_attributes=True)


class SaleBatchCreate(BaseModel):
    """POS checkout: several sales created in one atomic batch."""

    items: list[TransactionCreate] = Field(min_length=1, max_length=50)


class PaymentRow(BaseModel):
    id: int
    amount: Decimal
    method: str
    note: str
    recorded_by: str
    paid_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class BusinessHeader(BaseModel):
    """Shop identity printed at the top of a receipt."""

    name: str
    address: str
    phone: str
    currency: str
    receipt_note: str


class TransactionDetailOut(TransactionOut):
    """Everything one bill needs for a printable receipt."""

    product_name: str = ""
    product_sku: str = ""
    paid_total: Decimal = Decimal("0")
    due_amount: Decimal = Decimal("0")
    payments: list[PaymentRow] = []
    business: BusinessHeader = BusinessHeader(
        name="", address="", phone="", currency="", receipt_note=""
    )
