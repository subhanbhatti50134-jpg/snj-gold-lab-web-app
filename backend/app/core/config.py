
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
API_KEY = os.getenv("HISABPRO_API_KEY", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

# Comma-separated browser origins allowed to call the API.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

# Failed logins allowed per client+username per minute. 0 disables.
LOGIN_RATE_LIMIT = int(os.getenv("HISABPRO_LOGIN_RATE_LIMIT", "10"))

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from the project .env file")

if not API_KEY:
    raise RuntimeError("HISABPRO_API_KEY is missing from the project .env file")


if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is missing from the project .env file")
