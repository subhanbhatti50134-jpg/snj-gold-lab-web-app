import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import os

# Captured before the SQLite override below: PostgreSQL integration
# tests reconnect using this real URL when HISABPRO_PG_TESTS=1.
# Fall back to the project .env file when DATABASE_URL is not exported.
from pathlib import Path

from dotenv import dotenv_values

_PROJECT_ENV = Path(__file__).resolve().parents[2] / ".env"
PG_DATABASE_URL = os.environ.get("DATABASE_URL") or (
    dotenv_values(_PROJECT_ENV).get("DATABASE_URL", "")
)

# Set test configuration before importing the application.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["HISABPRO_API_KEY"] = "test-api-key"
os.environ["JWT_SECRET_KEY"] = "test-only-jwt-secret-key-not-for-production"
# Keep the shared in-memory login limiter out of the test suite.
os.environ["HISABPRO_LOGIN_RATE_LIMIT"] = "0"
# Keep test backups out of the real backup folder.
os.environ["HISABPRO_BACKUP_DIR"] = "/tmp/hisabpro-test-backups"
# Default to plaintext backups in tests so existing assertions hold.
# Encryption tests monkeypatch app.services.backup.BACKUP_KEY explicitly.
os.environ["HISABPRO_BACKUP_KEY"] = ""
# Keep pytest output clean; request-log tests raise the level via caplog.
os.environ["HISABPRO_LOG_LEVEL"] = "WARNING"
os.environ["HISABPRO_LOG_DIR"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # Register all ORM models
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(db):
    # The db fixture creates a fresh schema for each test.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client, db):
    """Return a function that logs in as a user with the given role."""
    from app.core.auth import hash_password
    from app.models.user import User

    password = "test-password-123"

    def _make(role: str = "admin") -> dict:
        username = f"test_{role}"
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            user = User(
                username=username,
                password_hash=hash_password(password),
                role=role,
                active=True,
            )
            db.add(user)
            db.commit()

        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make
