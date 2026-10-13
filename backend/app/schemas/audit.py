from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    id: int
    username: str
    action: str
    entity_type: str
    entity_id: str
    detail: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
