from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.permissions import ADMIN_ROLES, READ_ROLES, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.settings import SettingsOut, SettingsUpdate
from app.services.settings import get_settings, update_settings

router = APIRouter(prefix="/api/settings", tags=["Settings"])


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
