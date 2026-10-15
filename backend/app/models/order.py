
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now():
    return datetime.now(UTC)


class LayawayOrder(Base):
    """A bayana (advance booking): item agreed now, delivered later.

    The agreed rate is locked at booking time; delivery converts the
    order into a real sale with the advance applied as amount_paid.
    """

    __tablename__ = "layaway_orders"

    __table_args__ = (
        CheckConstraint(
            "estimated_weight_grams > 0 AND agreed_rate_per_gram > 0",
            name="ck_orders_terms",
        ),
        CheckConstraint(
            "estimated_total >= 0 AND advance_amount >= 0 "
            "AND advance_amount <= estimated_total",
            name="ck_orders_advance",
        ),
        CheckConstraint(
            "status IN ('pending', 'delivered', 'cancelled')",
            name="ck_orders_status",
        ),
        Index(
            "ix_layaway_orders_status_due",
            "status",
            "due_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(
        String(40), unique=True, index=True
    )

    party_id: Mapped[int | None] = mapped_column(
        ForeignKey("parties.id"), nullable=True, index=True
    )
    party_name: Mapped[str] = mapped_column(String(160), default="")

    description: Mapped[str] = mapped_column(String(300))
    estimated_weight_grams: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    agreed_rate_per_gram: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    estimated_total: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    advance_amount: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0")
    )

    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    # Set once the order is delivered; links to the sale it created.
    sale_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True
    )

    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def balance(self) -> Decimal:
        """Amount still expected on delivery (estimate minus advances)."""
        return Decimal(str(self.estimated_total)) - Decimal(
            str(self.advance_amount)
        )
