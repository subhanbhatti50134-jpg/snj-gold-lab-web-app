"""Idempotency support for money-moving POST endpoints.

A client sends an `Idempotency-Key` header (a UUID) with a checkout or
payment request. The key is claimed inside the SAME database transaction
as the business write, so:

* if the business write fails and rolls back, the key claim rolls back
  too and the client may safely retry with the same key;
* if the business write commits, the key commits with it and any later
  request with the same key replays the stored response instead of
  creating a duplicate.

Concurrent duplicates are settled by the unique constraint on `key`: the
loser of the race gets an IntegrityError, rolls back, and replays the
winner's stored response.
"""

import hashlib
import json
from dataclasses import dataclass

from fastapi import Header, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyKey

MAX_KEY_LENGTH = 64


def idempotency_key_header(
    key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str | None:
    """FastAPI dependency that pulls the optional Idempotency-Key header."""
    return key


def request_hash(payload) -> str:
    """Stable SHA-256 of the request body, independent of key order.

    Accepts a plain dict or a Pydantic model.
    """
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    canonical = json.dumps(
        payload, sort_keys=True, default=str, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class Replay:
    """A stored response to replay for a duplicate request."""

    status_code: int
    body: object


def _normalise_key(key: str | None) -> str | None:
    """Return a cleaned key, or None when the client sent none."""
    if key is None:
        return None
    key = key.strip()
    if not key:
        return None
    if len(key) > MAX_KEY_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Idempotency-Key must be at most {MAX_KEY_LENGTH} characters"
            ),
        )
    return key


def _replay_from(row: IdempotencyKey, digest: str) -> Replay:
    """Build a Replay from a stored row, validating the request matches."""
    if row.request_hash != digest:
        raise HTTPException(
            status_code=422,
            detail=(
                "This Idempotency-Key was already used with a "
                "different request body"
            ),
        )
    # status 0 means a previous request claimed the key but never stored
    # a response (it is still in flight, or the process died). Refusing
    # is safer than replaying an empty body.
    if row.response_status == 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "A request with this Idempotency-Key is still being "
                "processed. Retry shortly."
            ),
        )
    try:
        body = json.loads(row.response_body)
    except json.JSONDecodeError:
        body = None
    return Replay(status_code=row.response_status, body=body)


def begin(
    db: Session,
    *,
    key: str | None,
    user_id: int,
    endpoint: str,
    payload,
) -> Replay | None:
    """Claim `key` for this request, or return the replay to send.

    Must be called BEFORE the business write, inside the same
    transaction. Returns None when the key is new (or absent, in which
    case nothing is claimed and the endpoint behaves as before). The
    caller is then responsible for calling `record` before committing.
    """
    key = _normalise_key(key)
    if key is None:
        return None

    digest = request_hash(payload)

    existing = db.scalar(
        select(IdempotencyKey).where(IdempotencyKey.key == key)
    )
    if existing is not None:
        return _replay_from(existing, digest)

    try:
        db.add(
            IdempotencyKey(
                key=key,
                user_id=user_id,
                endpoint=endpoint,
                request_hash=digest,
                response_status=0,
                response_body="",
            )
        )
        db.flush()
    except IntegrityError:
        # Lost a concurrent race for the same key: drop our claim and
        # replay whatever the winner stored.
        db.rollback()
        winner = db.scalar(
            select(IdempotencyKey).where(IdempotencyKey.key == key)
        )
        if winner is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Could not claim the Idempotency-Key. Please retry."
                ),
            )
        return _replay_from(winner, digest)

    return None


def record(
    db: Session,
    *,
    key: str | None,
    status_code: int,
    body,
) -> None:
    """Store the response for `key` so a duplicate can replay it.

    A no-op when the client sent no key. Called after the business
    write succeeds, still inside the same transaction.
    """
    key = _normalise_key(key)
    if key is None:
        return

    row = db.scalar(
        select(IdempotencyKey).where(IdempotencyKey.key == key)
    )
    if row is None:
        return

    row.response_status = status_code
    # jsonable_encoder turns Pydantic models, Decimals and datetimes
    # into plain JSON types so the stored body can be replayed verbatim.
    row.response_body = json.dumps(jsonable_encoder(body), default=str)
