from datetime import datetime

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def log_audit(
    db: Session,
    *,
    username: str,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    detail: str = "",
) -> AuditLog:
    """Record an auditable change inside the caller's transaction.

    The row is only flushed, not committed: it becomes visible if and
    only if the surrounding business operation commits successfully.
    """
    entry = AuditLog(
        username=username,
        action=action,
        entity_type=entity_type,
        entity_id="" if entity_id is None else str(entity_id),
        detail=detail,
    )
    db.add(entry)
    return entry


def list_audit_logs(
    db: Session,
    *,
    username: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditLog]:
    statement = db.query(AuditLog)

    if username:
        statement = statement.filter(
            AuditLog.username.ilike(username.strip())
        )
    if action:
        statement = statement.filter(AuditLog.action == action.strip())
    if entity_type:
        statement = statement.filter(
            AuditLog.entity_type == entity_type.strip()
        )
    if date_from:
        statement = statement.filter(AuditLog.created_at >= date_from)
    if date_to:
        statement = statement.filter(AuditLog.created_at < date_to)

    return (
        statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
