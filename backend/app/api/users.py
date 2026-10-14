from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import hash_password
from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.user import User
from app.services.audit import log_audit

router = APIRouter(
    prefix="/api/users",
    tags=["User Management"],
)

Role = Literal["admin", "manager", "operator", "viewer"]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=256)
    role: Role = "operator"


class RoleUpdate(BaseModel):
    role: Role


class ActiveUpdate(BaseModel):
    active: bool


class PasswordUpdate(BaseModel):
    password: str = Field(min_length=12, max_length=256)


class UsernameUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=80)


def user_data(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "active": user.active,
        "created_at": user.created_at,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        active=True,
    )
    db.add(user)

    try:
        log_audit(
            db,
            username=admin.username,
            action="user.create",
            entity_type="user",
            detail=f"{data.username} as {data.role}",
        )
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from exc

    return user_data(user)


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    users = db.query(User).order_by(User.id).all()
    return [user_data(user) for user in users]


@router.patch("/{user_id}/role")
def update_user_role(
    user_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot change your own role",
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = data.role

    log_audit(
        db,
        username=admin.username,
        action="user.role_change",
        entity_type="user",
        entity_id=user.id,
        detail=f"{user.username} -> {data.role}",
    )
    db.commit()
    db.refresh(user)
    return user_data(user)


@router.patch("/{user_id}/active")
def update_user_active(
    user_id: int,
    data: ActiveUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    if user_id == admin.id and not data.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot deactivate your own account",
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.active = data.active

    log_audit(
        db,
        username=admin.username,
        action="user.active_change",
        entity_type="user",
        entity_id=user.id,
        detail=f"{user.username} -> active={data.active}",
    )
    db.commit()
    db.refresh(user)
    return user_data(user)


@router.patch("/{user_id}/password")
def update_user_password(
    user_id: int,
    data: PasswordUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """Admin reset of any user's password (including their own).

    The old password is never requested or logged; the new one is only
    ever stored as an argon2 hash.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(data.password)

    log_audit(
        db,
        username=admin.username,
        action="user.password_change",
        entity_type="user",
        entity_id=user.id,
        detail=f"password reset for {user.username}",
    )
    db.commit()
    db.refresh(user)
    return user_data(user)


@router.patch("/{user_id}/username")
def update_user_username(
    user_id: int,
    data: UsernameUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """Admin rename of any user (including their own).

    Safe for the logged-in admin: JWTs carry the user id, not the
    username, so an existing session survives the rename.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    old_username = user.username
    user.username = data.username

    try:
        log_audit(
            db,
            username=admin.username,
            action="user.username_change",
            entity_type="user",
            entity_id=user.id,
            detail=f"{old_username} -> {data.username}",
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from exc

    db.refresh(user)
    return user_data(user)
