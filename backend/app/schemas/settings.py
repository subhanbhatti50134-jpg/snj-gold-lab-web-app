from pydantic import BaseModel, RootModel


class SettingsOut(RootModel[dict[str, str]]):
    pass


class SettingsUpdate(RootModel[dict[str, str]]):
    pass


class SystemInfoOut(BaseModel):
    """Read-only system facts. Never contains secrets."""

    app_version: str
    database_backend: str
    backup_encrypted: bool
    backup_retention_days: int
    backup_keep_min: int
    login_rate_limit: int
    auto_create_tables: bool
