"""Phase 11 hardening: config validation and production schema control."""

import importlib

import pytest


@pytest.fixture(autouse=True)
def _restore_config():
    """Reload config before and after each test so re-imports never leak."""
    import app.core.config as config

    importlib.reload(config)
    yield
    importlib.reload(config)


def test_short_jwt_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "too-short")
    import app.core.config as config

    with pytest.raises(RuntimeError, match="at least 32 characters"):
        importlib.reload(config)


def test_long_jwt_secret_is_accepted(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 32)
    import app.core.config as config

    assert importlib.reload(config).JWT_SECRET_KEY == "x" * 32


def test_auto_create_tables_defaults_to_true(monkeypatch):
    monkeypatch.delenv("HISABPRO_AUTO_CREATE_TABLES", raising=False)
    import app.core.config as config

    assert importlib.reload(config).AUTO_CREATE_TABLES is True


def test_auto_create_tables_can_be_disabled(monkeypatch):
    monkeypatch.setenv("HISABPRO_AUTO_CREATE_TABLES", "false")
    import app.core.config as config

    assert importlib.reload(config).AUTO_CREATE_TABLES is False
