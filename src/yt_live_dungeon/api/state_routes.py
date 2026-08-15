import random
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.api.deps import get_current_time, get_session
from yt_live_dungeon.api.schemas.camp import (
    CampCandidateResponse,
    CampMemberResponse,
    CampStateResponse,
)
from yt_live_dungeon.api.schemas.enemy import RunEnemyResponse
from yt_live_dungeon.api.schemas.event import EventListResponse, EventResponse
from yt_live_dungeon.api.schemas.run_state import RunStateResponse
from yt_live_dungeon.domain.mp_regen import apply_mp_regen
from yt_live_dungeon.features.camp.deadline import ensure_camp_deadline_evaluated
from yt_live_dungeon.features.camp.state import CampStateData, get_camp_state
from yt_live_dungeon.features.waiting.deadline import ensure_waiting_deadline_evaluated
from yt_live_dungeon.persistence.queries.event import list_events_after
from yt_live_dungeon.persistence.queries.run import get_run
from yt_live_dungeon.persistence.queries.run_enemy import list_floor_enemies_with_master_data

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
    now: datetime = Depends(get_current_time),
) -> RunStateResponse:
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    # The GET route is the only entry point for state polling, so it must
    # itself evaluate (and, if needed, enforce) the CAMP and WAITING
    # deadlines rather than relying solely on the next command to notice
    # them -- there is no resident scheduler. This is the transaction
    # owner for those possible mutations; nothing upstream commits on
    # their behalf. Both calls are unconditionally safe regardless of
    # run.state: each no-ops unless it finds its own state (CAMP /
    # WAITING respectively), so at most one of them ever does anything
    # for a given run.
    await ensure_camp_deadline_evaluated(
        session, run_id, now=now, random_source=random.Random()
    )
    await ensure_waiting_deadline_evaluated(
        session, run_id, now=now, random_source=random.Random()
    )
    await session.commit()

    camp_state = await get_camp_state(session, run)

    floor_enemy_rows = await list_floor_enemies_with_master_data(session, run_id, run.current_floor)
    enemies = [
        RunEnemyResponse(
            id=run_enemy.id,
            enemy_key=enemy.enemy_key,
            display_name=enemy.display_name,
            role=run_enemy.role,
            order_in_group=run_enemy.order_in_group,
            max_hp=run_enemy.max_hp,
            hp=run_enemy.hp,
            max_mp=run_enemy.max_mp,
            # A pure, read-only projection to `now` -- never persisted
            # here. The DB column only actually advances the next time
            # this enemy acts (resolve_enemy_action()), but the value
            # shown to callers must always be the current logical MP,
            # not whatever was last durably written.
            mp=apply_mp_regen(
                mp=run_enemy.mp,
                max_mp=run_enemy.max_mp,
                regen_rate=run_enemy.mp_regen_rate,
                updated_at=run_enemy.mp_regen_updated_at,
                now=now,
            ).mp,
            attributes=run_enemy.attributes,
            is_alive=run_enemy.defeated_at is None,
        )
        for run_enemy, enemy in floor_enemy_rows
    ]

    return RunStateResponse(
        id=run.id,
        state=run.state,
        current_floor=run.current_floor,
        started_at=run.started_at,
        ended_at=run.ended_at,
        camp=_to_camp_response(camp_state),
        enemies=enemies,
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
