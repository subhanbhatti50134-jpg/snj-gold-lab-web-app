
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class MetalRate(Base):
    __tablename__ = "metal_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    metal: Mapped[str] = mapped_column(String(20), index=True)
    purity: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    # rate_per_gram is the normalized value used by all calculations.
    # unit/entered_rate preserve what the operator actually typed so
    # historical records stay readable if units change later.
    rate_per_gram: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    unit: Mapped[str] = mapped_column(String(20), default="gram")
    entered_rate: Mapped[Decimal] = mapped_column(
        Numeric(16, 4), default=Decimal("0")
    )
    source_note: Mapped[str] = mapped_column(String(250), default="")
    verified_by: Mapped[str] = mapped_column(String(120))
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
