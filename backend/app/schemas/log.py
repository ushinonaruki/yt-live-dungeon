import uuid
from datetime import datetime

from pydantic import BaseModel


class LogOut(BaseModel):
    id: int
    run_id: uuid.UUID
    event_type: str
    body: dict
    created_at: datetime

    model_config = {"from_attributes": True}
