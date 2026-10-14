from fastapi import APIRouter, Depends

from app.core.metrics import snapshot
from app.core.permissions import require_roles
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api", tags=["monitoring"])


@router.get("/metrics")
def get_metrics(
    admin: User = Depends(require_roles("admin")),
) -> dict:
    """In-process request counters and recent 5xx errors (admin only)."""
    return snapshot()
