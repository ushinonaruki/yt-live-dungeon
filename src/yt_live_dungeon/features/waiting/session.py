import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.waiting.deadline import ensure_waiting_deadline_evaluated
from yt_live_dungeon.persistence.models import Run, RunAdventurer, RunState
from yt_live_dungeon.persistence.queries.adventurer import get_adventurer_by_viewer
from yt_live_dungeon.persistence.queries.run import get_run, get_run_for_update

NOT_WAITING = "not_waiting"
NOT_JOINED = "not_joined"


@dataclass(frozen=True)
class ResolvedWaitingOnly:
    run: Run


@dataclass(frozen=True)
class ResolvedWaitingSession:
    run: Run
    adventurer: RunAdventurer


async def resolve_waiting_only(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    now: datetime,
    random_source: RandomSource,
    lock_run: bool = False,
) -> ResolvedWaitingOnly | CommandOutcome:
    """Preconditions shared by WAITING commands that don't require an
    already-joined adventurer (currently just @login): the initial-
    participation deadline is evaluated first (which may itself start
    floor 1 via start_run()), then run.state == WAITING must still hold.

    Mirrors features/camp/session.py's resolve_camp_only.
    """
    await ensure_waiting_deadline_evaluated(session, run_id, now=now, random_source=random_source)

    run = await (get_run_for_update(session, run_id) if lock_run else get_run(session, run_id))
    if run is None or run.state != RunState.WAITING:
        return CommandOutcome(processed=False, reason=NOT_WAITING, result=None)

    return ResolvedWaitingOnly(run=run)


async def resolve_waiting_session(
    session: AsyncSession,
    run_id: uuid.UUID,
    viewer_id: str,
    *,
    now: datetime,
    random_source: RandomSource,
    lock_run: bool = False,
) -> ResolvedWaitingSession | CommandOutcome:
    """Common preconditions shared by every WAITING command that acts on
    an already-joined adventurer: the deadline is evaluated first, then
    run.state == WAITING, and the viewer maps to a currently alive &
    participating RunAdventurer.

    Mirrors features/camp/session.py's resolve_camp_session.
    """
    resolved = await resolve_waiting_only(
        session, run_id, now=now, random_source=random_source, lock_run=lock_run
    )
    if isinstance(resolved, CommandOutcome):
        return resolved
    run = resolved.run

    adventurer = await get_adventurer_by_viewer(session, run_id, viewer_id)
    if adventurer is None or not adventurer.is_alive or not adventurer.is_participating:
        return CommandOutcome(processed=False, reason=NOT_JOINED, result=None)

    return ResolvedWaitingSession(run=run, adventurer=adventurer)
