from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.setting import Setting
from app.services.audit import log_audit

# Known settings and their defaults. Unknown keys are rejected so a typo
# cannot silently create a setting nobody reads.
DEFAULTS: dict[str, str] = {
    # Business profile (shown on printed reports and receipts)
    "business_name": "SNJ Gold Lab",
    "business_phone": "",
    "business_address": "",
    "currency": "PKR",
    # Inventory & trading defaults
    "default_location": "Main Store",
    "default_rate_unit": "tola",
    "allow_negative_stock": "false",
    # Warn on the inventory screen when a balance is at or below this
    # many grams. 0 disables the warning.
    "low_stock_threshold": "0",
    # Footer note printed on reports.
    "receipt_note": "",
}

BOOLEAN_KEYS = ("allow_negative_stock",)

# Enumerated values: key -> allowed values.
ENUM_KEYS: dict[str, tuple[str, ...]] = {
    "default_rate_unit": ("gram", "tola", "kilogram"),
}

# Numeric settings: key -> inclusive upper bound (must be >= 0).
NUMERIC_KEYS: dict[str, float] = {
    "low_stock_threshold": 1_000_000,
}

# Settings that may be left empty (optional profile fields).
OPTIONAL_KEYS = ("business_phone", "business_address", "receipt_note")


def get_settings(db: Session) -> dict[str, str]:
    """Return every known setting merged over its default value."""
    rows = db.scalars(select(Setting)).all()
    stored = {row.key: row.value for row in rows}

    result = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in stored:
            result[key] = stored[key]
    return result


def get_bool_setting(db: Session, key: str, default: bool = False) -> bool:
    if key not in DEFAULTS:
        return default

    row = db.get(Setting, key)
    if row is None:
        return DEFAULTS[key].lower() == "true"

    return row.value.strip().lower() == "true"


def validate_settings(payload: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}

    for key, value in payload.items():
        if key not in DEFAULTS:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown setting: {key}",
            )

        text = str(value).strip()

        if key in BOOLEAN_KEYS:
            if text.lower() not in {"true", "false"}:
                raise HTTPException(
                    status_code=422,
                    detail=f"{key} must be true or false",
                )
            text = text.lower()
        elif key in ENUM_KEYS:
            allowed = ENUM_KEYS[key]
            if text.lower() not in allowed:
                raise HTTPException(
                    status_code=422,
                    detail=f"{key} must be one of: {', '.join(allowed)}",
                )
            text = text.lower()
        elif key in NUMERIC_KEYS:
            try:
                number = float(text)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"{key} must be a number",
                ) from exc
            if number < 0 or number > NUMERIC_KEYS[key]:
                raise HTTPException(
                    status_code=422,
                    detail=f"{key} must be between 0 and {NUMERIC_KEYS[key]:g}",
                )
            text = f"{number:g}"
        elif key == "currency":
            if not text or len(text) > 10:
                raise HTTPException(
                    status_code=422,
                    detail="currency must be 1-10 characters",
                )
        elif key in OPTIONAL_KEYS:
            if len(text) > 255:
                raise HTTPException(
                    status_code=422,
                    detail=f"{key} must be at most 255 characters",
                )
        elif not text or len(text) > 255:
            raise HTTPException(
                status_code=422,
                detail=f"{key} must be 1-255 characters",
            )

        cleaned[key] = text

    return cleaned


def update_settings(
    db: Session,
    payload: dict[str, str],
    username: str,
) -> dict[str, str]:
    cleaned = validate_settings(payload)

    if not cleaned:
        raise HTTPException(status_code=422, detail="No settings provided")

    try:
        for key, value in cleaned.items():
            row = db.get(Setting, key)
            if row is None:
                row = Setting(key=key, value=value, updated_by=username)
                db.add(row)
            else:
                row.value = value
                row.updated_by = username

        log_audit(
            db,
            username=username,
            action="settings.update",
            entity_type="settings",
            detail=", ".join(sorted(cleaned)),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_settings(db)
