
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
API_KEY = os.getenv("HISABPRO_API_KEY", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from the project .env file")

if not API_KEY:
    raise RuntimeError("HISABPRO_API_KEY is missing from the project .env file")


if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is missing from the project .env file")
