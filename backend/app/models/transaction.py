
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now():
    return datetime.now(UTC)


class Transaction(Base):
    __tablename__ = "transactions"

    # DB-level guards so a raw SQL insert cannot bypass the API rules.
    # Movements (adjustments/transfers) legitimately use a zero rate and
    # total, so those are >= 0; weights must always be positive.
    __table_args__ = (
        CheckConstraint(
            "quantity_grams > 0 AND gross_weight_grams > 0 "
            "AND net_weight_grams > 0 AND deduction_grams >= 0",
            name="ck_transactions_weights",
        ),
        CheckConstraint(
            "purity >= 0 AND purity <= 100",
            name="ck_transactions_purity",
        ),
        CheckConstraint(
            "rate_per_gram >= 0 AND charges >= 0 "
            "AND total_amount >= 0 AND amount_paid >= 0 "
            "AND amount_paid <= total_amount",
            name="ck_transactions_amounts",
        ),
        Index(
            "ix_transactions_kind_status_date",
            "kind",
            "status",
            "transaction_date",
        ),
        Index(
            "ix_transactions_party_date",
            "party_id",
            "transaction_date",
        ),
    )

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
