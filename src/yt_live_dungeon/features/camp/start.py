import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.errors import CampConfigurationError
from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.persistence.models import RunCamp, RunCampMember, RunState
from yt_live_dungeon.persistence.queries.adventurer import list_active_participants
from yt_live_dungeon.persistence.queries.camp import get_camp_by_run_and_floor
from yt_live_dungeon.persistence.queries.egregore import list_active_pool_item_ids
from yt_live_dungeon.persistence.queries.event import append_event
from yt_live_dungeon.persistence.queries.run import get_run_for_update

CAMP_DURATION = timedelta(minutes=5)


async def start_camp(
    session: AsyncSession,
    run_id: uuid.UUID,
    egregore_id: int,
    *,
    now: datetime,
    random_source: RandomSource,
) -> RunCamp:
    """Start (or idempotently re-fetch) the CAMP for the run's current floor.

    Intended to be called from within the same transaction as whatever
    future Use Case persists a master's defeat -- it locks the run row but
    neither commits nor rolls back; the caller owns the transaction.
    """
    run = await get_run_for_update(session, run_id)

    existing = await get_camp_by_run_and_floor(session, run_id, run.current_floor)
    if existing is not None:
        return existing

    pool_item_ids = await list_active_pool_item_ids(session, egregore_id)
    if len(pool_item_ids) < 2:
        raise CampConfigurationError(
            f"egregore {egregore_id} has fewer than 2 active pool items"
        )

    candidate_a_item_id, candidate_b_item_id = random_source.sample(pool_item_ids, 2)

    camp = RunCamp(
        run_id=run_id,
        floor=run.current_floor,
        egregore_id=egregore_id,
        candidate_a_item_id=candidate_a_item_id,
        candidate_b_item_id=candidate_b_item_id,
        started_at=now,
        deadline_at=now + CAMP_DURATION,
        ended_at=None,
    )
    session.add(camp)

    participants = await list_active_participants(session, run_id)
    for adventurer in participants:
        session.add(
            RunCampMember(
                camp_id=camp.id,
                run_adventurer_id=adventurer.id,
                can_select_action=True,
                selected_action=None,
                selected_at=None,
                ready_at=None,
                left_at=None,
            )
        )

    run.state = RunState.CAMP

    await append_event(
        session,
        run_id,
        "camp_started",
        {
            "floor": run.current_floor,
            "egregore_id": egregore_id,
            "candidate_a_item_id": candidate_a_item_id,
            "candidate_b_item_id": candidate_b_item_id,
            "deadline_at": camp.deadline_at.isoformat(),
        },
    )

    return camp
