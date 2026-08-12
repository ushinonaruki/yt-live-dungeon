from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.floor.start import start_next_floor
from yt_live_dungeon.persistence.models import Run, RunCamp, RunState
from yt_live_dungeon.persistence.queries.adventurer import list_active_participants
from yt_live_dungeon.persistence.queries.event import append_event


async def end_camp(
    session: AsyncSession,
    run: Run,
    camp: RunCamp,
    *,
    now: datetime,
    reason: str,
    random_source: RandomSource,
) -> None:
    """Idempotently ends `camp` and transitions `run` onward: to BATTLE
    (next floor, carrying over currently participating adventurers) if
    any participant remains, or RETIRE if none do.

    Assumes the caller already holds a FOR UPDATE lock on `run` for this
    transaction and that `camp` belongs to run.current_floor. Never
    commits/rollbacks -- the caller (a CAMP command handler or the
    deadline evaluator) owns the transaction, having already decided
    termination is warranted; this function does not re-check readiness
    itself, only the ended_at idempotency guard.

    `reason` records why the caller ended the CAMP now (e.g. "all_ready",
    "timeout", "empty") on the camp_ended event, for observability only
    -- it does not change what this function does. `random_source` is
    only used when participants remain (to draw the next floor's saved
    next_group via start_next_floor()).
    """
    if camp.ended_at is not None:
        return

    participants = await list_active_participants(session, run.id)

    camp.ended_at = now
    await append_event(
        session,
        run.id,
        "camp_ended",
        {"floor": camp.floor, "reason": reason, "participant_count": len(participants)},
    )

    if not participants:
        run.state = RunState.RETIRE
        run.ended_at = now
        await append_event(session, run.id, "run_retired", {"floor": camp.floor})
        return

    await start_next_floor(session, run, participants, now=now, random_source=random_source)
