import uuid
from datetime import datetime

from pydantic import BaseModel


class CampCandidateResponse(BaseModel):
    item_id: int
    display_name: str


class CampMemberResponse(BaseModel):
    run_adventurer_id: uuid.UUID
    can_select_action: bool
    selected_action: str | None
    is_ready: bool
    is_participating: bool


class CampStateResponse(BaseModel):
    floor: int
    started_at: datetime
    deadline_at: datetime
    candidate_a: CampCandidateResponse
    candidate_b: CampCandidateResponse
    members: list[CampMemberResponse]
