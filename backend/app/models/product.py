
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now():
    return datetime.now(UTC)


class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        CheckConstraint(
            "purity >= 0 AND purity <= 100",
            name="ck_products_purity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    metal: Mapped[str] = mapped_column(String(20), index=True)
    purity: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("0")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
