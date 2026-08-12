import uuid
from datetime import datetime

from pydantic import BaseModel

from yt_live_dungeon.api.schemas.camp import CampStateResponse
from yt_live_dungeon.api.schemas.enemy import RunEnemyResponse
from yt_live_dungeon.persistence.models.run import RunState


class RunStateResponse(BaseModel):
    id: uuid.UUID
    state: RunState
    current_floor: int
    started_at: datetime
    ended_at: datetime | None
    camp: CampStateResponse | None = None
    # Only the current floor's RunEnemy rows -- a previous floor's
    # (defeated or not) enemies are never included. next_group is
    # deliberately not exposed here: obsidian/.../進行/キャンプ.md
    # section 9 leaves the public display range for NEXT undecided, and
    # there is no existing API contract basis for publishing it, so it
    # stays persisted (Run.next_group_id) and internally queryable only.
    enemies: list[RunEnemyResponse] = []
