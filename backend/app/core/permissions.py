from fastapi import Depends, HTTPException, status

from app.api.auth import get_current_user
from app.models.user import User

VALID_ROLES = {"admin", "manager", "operator", "viewer"}


def require_roles(*allowed_roles: str):
    if not allowed_roles:
        raise ValueError("At least one role must be specified")

    invalid_roles = set(allowed_roles) - VALID_ROLES
    if invalid_roles:
        raise ValueError(f"Invalid roles: {sorted(invalid_roles)}")

    def role_checker(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return user

    return role_checker


# Role groups used by API routers.
READ_ROLES = ("admin", "manager", "operator", "viewer")
OPERATE_ROLES = ("admin", "manager", "operator")
MANAGE_ROLES = ("admin", "manager")
ADMIN_ROLES = ("admin",)
