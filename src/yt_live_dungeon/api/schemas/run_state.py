import uuid
from datetime import datetime

from pydantic import BaseModel

from yt_live_dungeon.api.schemas.camp import CampStateResponse
from yt_live_dungeon.persistence.models.run import RunState


class RunStateResponse(BaseModel):
    id: uuid.UUID
    state: RunState
    current_floor: int
    started_at: datetime
    ended_at: datetime | None
    camp: CampStateResponse | None = None
