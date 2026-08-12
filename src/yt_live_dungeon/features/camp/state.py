import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import Run, RunState
from yt_live_dungeon.persistence.queries.camp import get_open_camp, list_camp_members
from yt_live_dungeon.persistence.queries.item import get_item


@dataclass(frozen=True)
class CampCandidateData:
    item_id: int
    display_name: str


@dataclass(frozen=True)
class CampMemberData:
    run_adventurer_id: uuid.UUID
    can_select_action: bool
    selected_action: str | None
    is_ready: bool
    is_participating: bool


@dataclass(frozen=True)
class CampStateData:
    floor: int
    started_at: datetime
    deadline_at: datetime
    candidate_a: CampCandidateData
    candidate_b: CampCandidateData
    members: list[CampMemberData]


async def get_camp_state(session: AsyncSession, run: Run) -> CampStateData | None:
    """The current CAMP's shared, structured state -- or None if the run
    isn't currently in an open CAMP. Never evaluates or ends the CAMP
    deadline; that's out of scope until CAMP end/next-floor handling."""
    if run.state != RunState.CAMP:
        return None

    camp = await get_open_camp(session, run.id, run.current_floor)
    if camp is None:
        return None

    candidate_a_item = await get_item(session, camp.candidate_a_item_id)
    candidate_b_item = await get_item(session, camp.candidate_b_item_id)

    member_rows = await list_camp_members(session, camp.id)

    return CampStateData(
        floor=camp.floor,
        started_at=camp.started_at,
        deadline_at=camp.deadline_at,
        candidate_a=CampCandidateData(
            item_id=candidate_a_item.id, display_name=candidate_a_item.display_name
        ),
        candidate_b=CampCandidateData(
            item_id=candidate_b_item.id, display_name=candidate_b_item.display_name
        ),
        members=[
            CampMemberData(
                run_adventurer_id=member.run_adventurer_id,
                can_select_action=member.can_select_action,
                selected_action=member.selected_action,
                is_ready=member.ready_at is not None,
                is_participating=adventurer.is_participating,
            )
            for member, adventurer in member_rows
        ],
    )
