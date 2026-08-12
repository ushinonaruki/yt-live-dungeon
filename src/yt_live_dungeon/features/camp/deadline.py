import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.camp.end import end_camp
from yt_live_dungeon.persistence.models import Run, RunState
from yt_live_dungeon.persistence.queries.camp import get_open_camp, list_camp_members
from yt_live_dungeon.persistence.queries.event import append_event
from yt_live_dungeon.persistence.queries.run import get_run, get_run_for_update


async def ensure_camp_deadline_evaluated(
    session: AsyncSession, run_id: uuid.UUID, *, now: datetime, random_source: RandomSource
) -> Run | None:
    """If the current floor's open CAMP has passed its deadline, forces
    ready_at on every still-participating, not-yet-ready member and ends
    the CAMP -- all within this call, so any precondition check the
    caller performs afterward already sees the post-timeout state.

    Cheap in the common case: an unlocked read decides whether anything
    needs to happen at all, and the run row is only locked FOR UPDATE
    once the deadline has actually passed, preserving the existing
    no-lock behavior of read-only CAMP commands (@status/@bag/@move/
    spell commands) when there is nothing to enforce.

    Never commits/rollbacks -- the caller owns the transaction.
    """
    run = await get_run(session, run_id)
    if run is None or run.state != RunState.CAMP:
        return run

    camp = await get_open_camp(session, run_id, run.current_floor)
    if camp is None or now < camp.deadline_at:
        return run

    run = await get_run_for_update(session, run_id)
    camp = await get_open_camp(session, run_id, run.current_floor)
    if camp is None or camp.ended_at is not None or now < camp.deadline_at:
        return run

    members = await list_camp_members(session, camp.id)
    for member, adventurer in members:
        if adventurer.is_participating and member.ready_at is None:
            member.ready_at = now
            await append_event(
                session,
                run_id,
                "adventurer_ready",
                {"adventurer": str(adventurer.id), "reason": "timeout"},
            )

    await end_camp(session, run, camp, now=now, reason="timeout", random_source=random_source)
    return run
