import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.api.deps import get_session
from yt_live_dungeon.api.schemas.camp import (
    CampCandidateResponse,
    CampMemberResponse,
    CampStateResponse,
)
from yt_live_dungeon.api.schemas.event import EventListResponse, EventResponse
from yt_live_dungeon.api.schemas.run_state import RunStateResponse
from yt_live_dungeon.features.camp.deadline import ensure_camp_deadline_evaluated
from yt_live_dungeon.features.camp.state import CampStateData, get_camp_state
from yt_live_dungeon.persistence.queries.event import list_events_after
from yt_live_dungeon.persistence.queries.run import get_run

router = APIRouter()


def _to_camp_response(camp_state: CampStateData | None) -> CampStateResponse | None:
    if camp_state is None:
        return None

    return CampStateResponse(
        floor=camp_state.floor,
        started_at=camp_state.started_at,
        deadline_at=camp_state.deadline_at,
        candidate_a=CampCandidateResponse(
            item_id=camp_state.candidate_a.item_id,
            display_name=camp_state.candidate_a.display_name,
        ),
        candidate_b=CampCandidateResponse(
            item_id=camp_state.candidate_b.item_id,
            display_name=camp_state.candidate_b.display_name,
        ),
        members=[
            CampMemberResponse(
                run_adventurer_id=member.run_adventurer_id,
                can_select_action=member.can_select_action,
                selected_action=member.selected_action,
                is_ready=member.is_ready,
                is_participating=member.is_participating,
            )
            for member in camp_state.members
        ],
    )


@router.get(
    "/api/v1/runs/{run_id}/state",
    response_model=RunStateResponse,
    responses={404: {"description": "Run not found"}},
)
async def get_run_state(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> RunStateResponse:
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    # The GET route is the only entry point for state polling, so it must
    # itself evaluate (and, if needed, enforce) the CAMP deadline rather
    # than relying solely on the next command to notice it -- there is no
    # resident scheduler. This is the transaction owner for that possible
    # mutation; nothing upstream commits on its behalf.
    await ensure_camp_deadline_evaluated(session, run_id, now=datetime.now(UTC))
    await session.commit()

    camp_state = await get_camp_state(session, run)

    return RunStateResponse(
        id=run.id,
        state=run.state,
        current_floor=run.current_floor,
        started_at=run.started_at,
        ended_at=run.ended_at,
        camp=_to_camp_response(camp_state),
    )


@router.get(
    "/api/v1/runs/{run_id}/events",
    response_model=EventListResponse,
    responses={404: {"description": "Run not found"}},
)
async def get_run_events(
    run_id: uuid.UUID,
    after: int = 0,
    session: AsyncSession = Depends(get_session),
) -> EventListResponse:
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    events = await list_events_after(session, run_id, after)

    return EventListResponse(
        events=[
            EventResponse(
                sequence=event.sequence,
                event_type=event.event_type,
                body=event.body,
                created_at=event.created_at,
            )
            for event in events
        ]
    )
