from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import READ_ROLES, require_roles
from app.db.session import get_db
from app.services.dashboard import get_dashboard

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get(
    "",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def dashboard(db: Session = Depends(get_db)):
    return get_dashboard(db)
