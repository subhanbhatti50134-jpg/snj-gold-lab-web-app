import json
import os
import re
import subprocess
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app.core.config import DATABASE_URL, ROOT_DIR
from app.models.metal_rate import MetalRate
from app.models.payments import Payment
from app.models.party import Party
from app.models.product import Product
from app.models.setting import Setting
from app.models.stock_movement import StockMovement
from app.models.transaction import Transaction
from app.models.user import User

# Backups live outside the repository by default so a `git clean`
# can never delete them. Override with HISABPRO_BACKUP_DIR.
BACKUP_DIR = Path(
    os.getenv("HISABPRO_BACKUP_DIR", str(ROOT_DIR / "backups"))
)

FILENAME_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(?:dump|json)$"
)
TIMEOUT_SECONDS = 300

# JSON backup: portable export/import of every business table.
# Parents come first (insert order); restore deletes in reverse.
JSON_FORMAT = "snj-gold-lab-backup"
JSON_VERSION = 1
JSON_MODELS = [
    User,
    Setting,
    Product,
    Party,
    MetalRate,
    Transaction,
    Payment,
    StockMovement,
]


def _connection_uri() -> str:
    # pg_dump understands postgresql://, not SQLAlchemy's driver suffix.
    return DATABASE_URL.replace("postgresql+psycopg", "postgresql", 1)


def _safe_path(filename: str) -> Path:
    """Resolve a backup file name, refusing anything suspicious."""
    if not FILENAME_PATTERN.match(filename):
        raise HTTPException(
            status_code=422,
            detail="Invalid backup file name",
        )

    path = (BACKUP_DIR / filename).resolve()

    if path.parent != BACKUP_DIR.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")

    return path


def _safe_json_path(filename: str) -> Path:
    if not filename.endswith(".json"):
        raise HTTPException(status_code=422, detail="Not a JSON backup file")
    return _safe_path(filename)


def _run(command: list[str]) -> None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="PostgreSQL tools (pg_dump/pg_restore) are not installed",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=500,
            detail="Backup or restore timed out",
        ) from exc

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"PostgreSQL command failed: {result.stderr.strip()[:500]}",
        )


def list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []

    paths = list(BACKUP_DIR.glob("*.dump")) + list(
        BACKUP_DIR.glob("*.json")
    )

    items = []
    for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
        stat = path.stat()
        items.append(
            {
                "filename": path.name,
                "size_bytes": stat.st_size,
                "kind": "json" if path.suffix == ".json" else "pgdump",
                "created_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ),
            }
        )
    return items


def create_backup() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    filename = (
        f"hisabpro-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.dump"
    )
    destination = BACKUP_DIR / filename

    _run(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--file",
            str(destination),
            _connection_uri(),
        ]
    )

    stat = destination.stat()

    return {
        "filename": filename,
        "size_bytes": stat.st_size,
        "kind": "pgdump",
        "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
    }


def restore_backup(filename: str, confirm: str) -> dict:
    if confirm != filename:
        raise HTTPException(
            status_code=422,
            detail="Restore confirmation must match the backup file name",
        )

    path = _safe_path(filename)

    # --clean drops existing objects before restoring, so this
    # overwrites the current database. The confirm flag is mandatory.
    _run(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--dbname",
            _connection_uri(),
            str(path),
        ]
    )

    return {
        "filename": filename,
        "restored": True,
        "restored_at": datetime.now(timezone.utc),
    }


def _columns(model) -> list[tuple[str, type]]:
    """Column keys and Python types for a model, in declaration order."""
    return [
        (column.key, column.type.python_type)
        for column in inspect(model).mapper.columns
    ]


def _encode(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _decode(value, python_type):
    if value is None:
        return None
    if python_type is Decimal:
        return Decimal(str(value))
    if python_type is datetime:
        return datetime.fromisoformat(value)
    if python_type is date:
        return date.fromisoformat(value)
    return value


def _primary_key_name(model) -> str:
    return inspect(model).mapper.primary_key[0].key


def create_json_backup(db: Session) -> dict:
    """Export every business table into a single portable JSON file."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    data: dict[str, list[dict]] = {}
    counts: dict[str, int] = {}

    for model in JSON_MODELS:
        table = model.__tablename__
        pk = _primary_key_name(model)
        rows = db.execute(
            select(model).order_by(getattr(model, pk))
        ).scalars()
        columns = _columns(model)
        data[table] = [
            {key: _encode(getattr(row, key)) for key, _ in columns}
            for row in rows
        ]
        counts[table] = len(data[table])

    payload = {
        "format": JSON_FORMAT,
        "version": JSON_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "data": data,
    }

    filename = (
        f"snj-gold-lab-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json"
    )
    destination = BACKUP_DIR / filename
    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    stat = destination.stat()

    return {
        "filename": filename,
        "size_bytes": stat.st_size,
        "kind": "json",
        "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        "counts": counts,
    }


def restore_json_backup(db: Session, filename: str, confirm: str) -> dict:
    """Replace all business data with the contents of a JSON backup.

    Runs inside a single transaction: either the whole restore lands or
    nothing does. The audit log is intentionally kept and one new entry
    is written for the restore itself.
    """
    if confirm != filename:
        raise HTTPException(
            status_code=422,
            detail="Restore confirmation must match the backup file name",
        )

    path = _safe_json_path(filename)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Backup file could not be read as JSON",
        ) from exc

    if (
        not isinstance(payload, dict)
        or payload.get("format") != JSON_FORMAT
        or payload.get("version") != JSON_VERSION
    ):
        raise HTTPException(
            status_code=422,
            detail="File is not a valid SNJ Gold Lab JSON backup",
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=422,
            detail="Backup file is missing its data section",
        )

    counts: dict[str, int] = {}

    try:
        # Children first so foreign keys never block the wipe.
        for model in reversed(JSON_MODELS):
            db.execute(delete(model))
        # Push the deletes to the database and drop the old rows from the
        # session identity map so re-inserting the same primary keys is
        # treated as fresh inserts (required on PostgreSQL).
        db.flush()
        db.expunge_all()

        # Insert parents before children and flush after every table so a
        # child row (e.g. payments) never references a parent that has not
        # been written yet. JSON_MODELS is already ordered parent-first.
        for model in JSON_MODELS:
            table = model.__tablename__
            rows = data.get(table, [])
            if not isinstance(rows, list):
                raise HTTPException(
                    status_code=422,
                    detail=f"Backup table '{table}' is not a list",
                )

            columns = _columns(model)
            for row in rows:
                if not isinstance(row, dict):
                    raise HTTPException(
                        status_code=422,
                        detail=f"Backup table '{table}' has invalid rows",
                    )
                db.add(
                    model(
                        **{
                            key: _decode(row[key], python_type)
                            for key, python_type in columns
                            if key in row
                        }
                    )
                )
            db.flush()
            counts[table] = len(rows)

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Restore failed, no changes were made: {exc}",
        ) from exc

    return {
        "filename": filename,
        "restored": True,
        "restored_at": datetime.now(timezone.utc),
        "counts": counts,
    }
