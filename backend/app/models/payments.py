
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Payment(Base):
    __tablename__ = "payments"

    # Positive = money received, negative = refund posted on cancel.
    # Zero is never a meaningful ledger entry.
    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_payments_amount_nonzero"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id"),
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    method: Mapped[str] = mapped_column(String(30), default="cash")
    note: Mapped[str] = mapped_column(Text, default="")
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    recorded_by: Mapped[str] = mapped_column(String(120))
