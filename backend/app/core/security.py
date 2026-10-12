
import secrets

from fastapi import Header, HTTPException, status

from app.core.config import API_KEY


def require_api_key(
    x_api_key: str = Header(default="", alias="X-API-Key"),
):
    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
