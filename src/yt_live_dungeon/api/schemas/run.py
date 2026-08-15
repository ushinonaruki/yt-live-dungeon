import uuid
from datetime import datetime

from pydantic import BaseModel

from yt_live_dungeon.persistence.models.run import RunState


class RunCreateResponse(BaseModel):
    id: uuid.UUID
    state: RunState
    current_floor: int
    started_at: datetime
    waiting_deadline_at: datetime | None
