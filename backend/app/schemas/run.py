import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.run import RunState


class RunOut(BaseModel):
    id: uuid.UUID
    state: RunState
    current_floor: int
    total_deaths: int
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PendingJoinOut(BaseModel):
    id: uuid.UUID
    youtube_id: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AdventurerOut(BaseModel):
    id: uuid.UUID
    youtube_id: str
    nickname: str
    hp: int
    max_hp: int
    is_alive: bool
    joined_floor: int

    model_config = {"from_attributes": True}


class EnemyOut(BaseModel):
    id: uuid.UUID
    enemy_id: int
    display_name: str
    floor: int
    hp: int
    max_hp: int
    barrier: int
    position: int
    role: str
    is_alive: bool

    model_config = {"from_attributes": True}


class RunStateOut(BaseModel):
    run_id: uuid.UUID
    state: RunState
    current_floor: int
    total_deaths: int
    pending_join_count: int
    pending_joins: list[PendingJoinOut]
    adventurers: list[AdventurerOut]
    enemies: list[EnemyOut]


class FloorStartResult(BaseModel):
    run_id: uuid.UUID
    floor: int
    adventurer_count: int
    enemy_count: int
