
import base64
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
API_KEY = os.getenv("HISABPRO_API_KEY", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

# Optional: base64-encoded 32-byte AES-256 key. When set, new backups
# are encrypted at rest (*.json.enc / *.dump.enc). When unset, backups
# stay plaintext (development convenience). Generate with:
#   python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
BACKUP_KEY = os.getenv("HISABPRO_BACKUP_KEY", "")

# Backups older than this many days are pruned after each new backup,
# but the newest BACKUP_KEEP_MIN files are always kept.
BACKUP_RETENTION_DAYS = int(os.getenv("HISABPRO_BACKUP_RETENTION_DAYS", "30"))
BACKUP_KEEP_MIN = int(os.getenv("HISABPRO_BACKUP_KEEP_MIN", "5"))

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

# Logging: level always applies; file logging only when LOG_DIR is set
# (docker compose points this at a persistent volume). Empty = stdout only.
LOG_LEVEL = os.getenv("HISABPRO_LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("HISABPRO_LOG_DIR", "").strip()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from the project .env file")

if not API_KEY:
    raise RuntimeError("HISABPRO_API_KEY is missing from the project .env file")


if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is missing from the project .env file")

if len(JWT_SECRET_KEY) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY must be at least 32 characters. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )

if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    raise RuntimeError(
        "HISABPRO_LOG_LEVEL must be one of DEBUG, INFO, WARNING, "
        f"ERROR, CRITICAL (got {LOG_LEVEL!r})"
    )

# Development convenience: create tables on startup when True.
# Production (docker-compose sets this to false) must use Alembic
# migrations only so the schema is always migration-controlled.
AUTO_CREATE_TABLES = os.getenv("HISABPRO_AUTO_CREATE_TABLES", "true").lower() in {
    "1",
    "true",
    "yes",
}

if BACKUP_KEY:
    try:
        decoded_key = base64.b64decode(BACKUP_KEY, validate=True)
    except Exception as exc:
        raise RuntimeError(
            "HISABPRO_BACKUP_KEY must be valid base64. "
            'Generate one with: python -c "import base64,secrets; '
            'print(base64.b64encode(secrets.token_bytes(32)).decode())"'
        ) from exc

    if len(decoded_key) != 32:
        raise RuntimeError(
            "HISABPRO_BACKUP_KEY must decode to exactly 32 bytes "
            "(AES-256). Generate one with: python -c \"import base64,secrets; "
            "print(base64.b64encode(secrets.token_bytes(32)).decode())\""
        )
