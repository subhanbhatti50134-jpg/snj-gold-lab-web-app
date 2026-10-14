from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import (
    AUTO_CREATE_TABLES,
    BACKUP_KEEP_MIN,
    BACKUP_KEY,
    BACKUP_RETENTION_DAYS,
    DATABASE_URL,
    LOGIN_RATE_LIMIT,
)
from app.core.permissions import ADMIN_ROLES, READ_ROLES, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.settings import SettingsOut, SettingsUpdate, SystemInfoOut
from app.services.settings import get_settings, update_settings

router = APIRouter(prefix="/api/settings", tags=["Settings"])

APP_VERSION = "1.0.0"


@router.get(
    "",
    response_model=SettingsOut,
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def read_settings(db: Session = Depends(get_db)):
    return get_settings(db)


@router.put("", response_model=SettingsOut)
def write_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    return update_settings(db, payload.root, user.username)


@router.get(
    "/system",
    response_model=SystemInfoOut,
    dependencies=[Depends(require_roles(*ADMIN_ROLES))],
)
def read_system_info():
    """Read-only system facts for the settings page.

    Deliberately exposes no secrets: only the database engine name
    (never the URL), whether backups are encrypted (never the key), and
    non-sensitive operational limits.
    """
    scheme = DATABASE_URL.split("://", 1)[0].split("+", 1)[0] if DATABASE_URL else "unknown"

    return {
        "app_version": APP_VERSION,
        "database_backend": scheme,
        "backup_encrypted": bool(BACKUP_KEY),
        "backup_retention_days": BACKUP_RETENTION_DAYS,
        "backup_keep_min": BACKUP_KEEP_MIN,
        "login_rate_limit": LOGIN_RATE_LIMIT,
        "auto_create_tables": AUTO_CREATE_TABLES,
    }
