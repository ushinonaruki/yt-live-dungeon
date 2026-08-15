import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.run.start import start_run
from yt_live_dungeon.persistence.models import Run, RunState
from yt_live_dungeon.persistence.queries.adventurer import list_active_participants
from yt_live_dungeon.persistence.queries.event import append_event
from yt_live_dungeon.persistence.queries.run import get_run, get_run_for_update

# NOTE (open question, deliberately left unresolved -- see the task's
# final report): obsidian/.../進行/参加受付.md does not define what
# should happen if the initial-participation deadline is reached while
# zero participants remain. Guessing a terminal state or an automatic
# floor start here would invent behavior the spec doesn't sanction. The
# safe, minimal choice made here is to do nothing beyond leaving
# run.state at WAITING -- in particular, never spawning a floor 1 battle
# with no adventurers on it.


async def ensure_waiting_deadline_evaluated(
    session: AsyncSession, run_id: uuid.UUID, *, now: datetime, random_source: RandomSource
) -> Run | None:
    """If `run_id`'s initial-participation deadline has passed, forces
    waiting_ready_at on every still-participating, not-yet-ready
    adventurer, then starts floor 1 via start_run() if at least one
    participant remains -- all within this call, so any precondition
    check the caller performs afterward already sees the post-timeout
    state.

    Per obsidian/.../進行/参加受付.md section 6, the deadline itself only
    exists once the first successful @login has set run.waiting_deadline_at;
    a run with no login yet has nothing to evaluate and is left untouched.

    Cheap in the common case: an unlocked read decides whether anything
    needs to happen at all, and the run row is only locked FOR UPDATE
    once the deadline has actually passed, preserving the existing no-
    lock behavior of read-only WAITING commands when there is nothing to
    enforce (mirrors features/camp/deadline.py's ensure_camp_deadline_evaluated).

    Never commits/rollbacks -- the caller owns the transaction.
    """
    run = await get_run(session, run_id)
    if run is None or run.state != RunState.WAITING:
        return run

    if run.waiting_deadline_at is None or now < run.waiting_deadline_at:
        return run

    run = await get_run_for_update(session, run_id)
    if (
        run.state != RunState.WAITING
        or run.waiting_deadline_at is None
        or now < run.waiting_deadline_at
    ):
        return run

    participants = await list_active_participants(session, run_id)
    for adventurer in participants:
        if adventurer.waiting_ready_at is None:
            adventurer.waiting_ready_at = now
            await append_event(
                session,
                run_id,
                "adventurer_ready",
                {"adventurer": str(adventurer.id), "reason": "timeout"},
            )

    if participants:
        await start_run(session, run, now=now, random_source=random_source)

    return run
