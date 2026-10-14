from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.permissions import ADMIN_ROLES, require_roles
from app.db.session import get_db
from app.models.user import User
from app.services import backup as backup_service
from app.services.audit import log_audit

router = APIRouter(prefix="/api/backups", tags=["Database Backup"])


class RestoreRequest(BaseModel):
    confirm: str = Field(min_length=1, max_length=255)


class BackupOut(BaseModel):
    filename: str
    size_bytes: int
    kind: Literal["pgdump", "json"] = "pgdump"
    encrypted: bool = False
    created_at: datetime


class JsonBackupOut(BackupOut):
    kind: Literal["json"] = "json"
    counts: dict[str, int] | None = None


class RestoreOut(BaseModel):
    filename: str
    restored: bool
    restored_at: datetime
    counts: dict[str, int] | None = None


@router.get(
    "",
    response_model=list[BackupOut],
    dependencies=[Depends(require_roles(*ADMIN_ROLES))],
)
def get_backups():
    return backup_service.list_backups()


@router.post(
    "",
    response_model=BackupOut,
    status_code=status.HTTP_201_CREATED,
)
def create_backup(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    result = backup_service.create_backup()
    pruned = result.pop("pruned", [])

    log_audit(
        db,
        username=user.username,
        action="backup.create",
        entity_type="database",
        entity_id=result["filename"],
        detail=f"size {result['size_bytes']} bytes",
    )
    for name in pruned:
        log_audit(
            db,
            username=user.username,
            action="backup.prune",
            entity_type="database",
            entity_id=name,
            detail="backup pruned by retention policy",
        )
    db.commit()

    return result


@router.post(
    "/{filename}/restore",
    response_model=RestoreOut,
)
def restore_backup(
    filename: str,
    payload: RestoreRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Overwrite the current database with a backup file.

    The restore only runs when `confirm` exactly matches the file name,
    and every restore is written to the audit log afterwards.
    """
    result = backup_service.restore_backup(filename, payload.confirm)

    log_audit(
        db,
        username=user.username,
        action="backup.restore",
        entity_type="database",
        entity_id=filename,
        detail="database restored from backup",
    )
    db.commit()

    return result


@router.post(
    "/json",
    response_model=JsonBackupOut,
    status_code=status.HTTP_201_CREATED,
)
def create_json_backup(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Export all business data to a portable JSON backup file."""
    result = backup_service.create_json_backup(db)
    pruned = result.pop("pruned", [])

    log_audit(
        db,
        username=user.username,
        action="backup.create.json",
        entity_type="database",
        entity_id=result["filename"],
        detail="JSON data backup created",
    )
    for name in pruned:
        log_audit(
            db,
            username=user.username,
            action="backup.prune",
            entity_type="database",
            entity_id=name,
            detail="backup pruned by retention policy",
        )
    db.commit()

    return result


@router.get(
    "/json/{filename}/download",
    dependencies=[Depends(require_roles(*ADMIN_ROLES))],
)
def download_json_backup(filename: str):
    """Download a JSON backup file so it can be stored off the server."""
    path = backup_service._safe_json_path(filename)
    media_type = (
        "application/octet-stream"
        if filename.endswith(".enc")
        else "application/json"
    )
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
    )


@router.post(
    "/json/{filename}/restore",
    response_model=RestoreOut,
)
def restore_json_backup(
    filename: str,
    payload: RestoreRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Replace all business data with the contents of a JSON backup.

    The restore only runs when `confirm` exactly matches the file name,
    and every restore is written to the audit log afterwards.
    """
    result = backup_service.restore_json_backup(
        db, filename, payload.confirm
    )

    log_audit(
        db,
        username=user.username,
        action="backup.restore.json",
        entity_type="database",
        entity_id=filename,
        detail="data restored from JSON backup",
    )
    db.commit()

    return result
