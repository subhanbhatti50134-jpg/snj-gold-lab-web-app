from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.auth import (
    create_access_token,
    decode_access_token,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (InvalidTokenError, ValueError, KeyError, TypeError):
        raise unauthorized

    user = db.get(User, user_id)

    if user is None or not user.active:
        raise unauthorized

    return user


@router.post("/login")
def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    # Limit failed attempts per client+username to slow down guessing.
    client = request.client.host if request.client else "unknown"
    limit_key = f"{client}:{data.username.strip().lower()}"

    if ratelimit.is_blocked(limit_key):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in a minute.",
        )

    user = db.query(User).filter(User.username == data.username).first()

    if (
        user is None
        or not user.active
        or not verify_password(data.password, user.password_hash)
    ):
        ratelimit.record_failure(limit_key)
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
        )

    ratelimit.clear_failures(limit_key)

    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "expires_in": 1800,
    }


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "active": user.active,
    }
