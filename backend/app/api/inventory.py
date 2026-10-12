from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import READ_ROLES, require_roles
from app.db.session import get_db
from app.services.inventory import get_inventory

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])


@router.get(
    "",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def list_inventory(
    location: str | None = None,
    db: Session = Depends(get_db),
):
    return get_inventory(db, location)
