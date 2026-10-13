
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class IdempotencyKey(Base):
    """One row per client-supplied idempotency key.

    A POS double-click or a network retry re-sends the same key. The
    first request that commits wins and stores its response here; any
    later request with the same key gets that stored response replayed
    instead of creating a duplicate sale or payment.
    """

    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The client-generated key (a UUID). Unique so two concurrent
    # requests with the same key cannot both commit.
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Scopes the key to the user who created it, so one user's key can
    # never collide with another's.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True
    )

    # Which endpoint the key was used on, e.g. "POST /api/sales/batch".
    endpoint: Mapped[str] = mapped_column(String(120))

    # SHA-256 of the canonical request body. Reusing a key with a
    # DIFFERENT body is a client bug, so it is rejected (422) instead
    # of silently replaying an unrelated response.
    request_hash: Mapped[str] = mapped_column(String(64))

    # The stored response, replayed verbatim on a duplicate request.
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
