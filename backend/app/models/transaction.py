
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date, DateTime, ForeignKey, Index, Numeric, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(
        String(40), unique=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(30), index=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id")
    )
    party_id: Mapped[int | None] = mapped_column(
        ForeignKey("parties.id"), nullable=True, index=True
    )

    quantity_grams: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    gross_weight_grams: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    net_weight_grams: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    deduction_grams: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    purity: Mapped[Decimal] = mapped_column(Numeric(8, 4))

    rate_id: Mapped[int | None] = mapped_column(
        ForeignKey("metal_rates.id"), nullable=True
    )
    rate_per_gram: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    charges: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0")
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0")
    )

    party_name: Mapped[str] = mapped_column(String(160), default="")
    location: Mapped[str] = mapped_column(String(100), default="Main Store")
    destination: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120))

    # "active" rows feed reports; "cancelled" rows are kept for audit
    # history and are excluded from balances and stock.
    status: Mapped[str] = mapped_column(
        String(20), default="active", index=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_by: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    # The business date the user chose; reports filter on this, not on
    # the row-creation timestamp.
    transaction_date: Mapped[date] = mapped_column(
        Date, default=date.today, index=True
    )
