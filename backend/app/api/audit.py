from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.permissions import ADMIN_ROLES, require_roles
from app.db.session import get_db
from app.schemas.audit import AuditLogOut
from app.services.audit import list_audit_logs

router = APIRouter(prefix="/api/audit", tags=["Audit Logs"])


@router.get(
    "",
    response_model=list[AuditLogOut],
    dependencies=[Depends(require_roles(*ADMIN_ROLES))],
)
def get_audit_logs(
    username: str | None = Query(default=None, min_length=1, max_length=120),
    action: str | None = Query(default=None, min_length=1, max_length=60),
    entity_type: str | None = Query(
        default=None, min_length=1, max_length=60
    ),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from cannot be later than date_to",
        )

    start = datetime.combine(date_from, time.min) if date_from else None
    end = (
        datetime.combine(date_to + timedelta(days=1), time.min)
        if date_to
        else None
    )

    return list_audit_logs(
        db,
        username=username,
        action=action,
        entity_type=entity_type,
        date_from=start,
        date_to=end,
        skip=skip,
        limit=limit,
    )
