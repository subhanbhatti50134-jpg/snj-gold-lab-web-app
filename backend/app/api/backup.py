from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.permissions import ADMIN_ROLES, require_roles
from app.services.audit import log_audit
from app.db.session import get_db
from app.models.user import User
from app.services import backup as backup_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/backups", tags=["Database Backup"])


class RestoreRequest(BaseModel):
    confirm: str = Field(min_length=1, max_length=255)


class BackupOut(BaseModel):
    filename: str
    size_bytes: int
    created_at: datetime


class RestoreOut(BaseModel):
    filename: str
    restored: bool
    restored_at: datetime


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

    log_audit(
        db,
        username=user.username,
        action="backup.create",
        entity_type="database",
        entity_id=result["filename"],
        detail=f"size {result['size_bytes']} bytes",
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
