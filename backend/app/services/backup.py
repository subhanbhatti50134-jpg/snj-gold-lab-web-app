import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from app.core.config import DATABASE_URL, ROOT_DIR

# Backups live outside the repository by default so a `git clean`
# can never delete them. Override with HISABPRO_BACKUP_DIR.
BACKUP_DIR = Path(
    os.getenv("HISABPRO_BACKUP_DIR", str(ROOT_DIR / "backups"))
)

FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.dump$")
TIMEOUT_SECONDS = 300


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

    items = []
    for path in sorted(BACKUP_DIR.glob("*.dump"), reverse=True):
        stat = path.stat()
        items.append(
            {
                "filename": path.name,
                "size_bytes": stat.st_size,
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
