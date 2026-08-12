import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.features.camp.deadline import ensure_camp_deadline_evaluated
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.persistence.models import Run, RunAdventurer, RunCamp, RunState
from yt_live_dungeon.persistence.queries.adventurer import get_adventurer_by_viewer
from yt_live_dungeon.persistence.queries.camp import get_open_camp
from yt_live_dungeon.persistence.queries.run import get_run, get_run_for_update

NOT_IN_CAMP = "not_in_camp"
NOT_JOINED = "not_joined"


@dataclass(frozen=True)
class ResolvedCampOnly:
    run: Run
    camp: RunCamp


@dataclass(frozen=True)
class ResolvedCampSession:
    run: Run
    camp: RunCamp
    adventurer: RunAdventurer


async def resolve_camp_only(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    now: datetime,
    lock_run: bool = False,
) -> ResolvedCampOnly | CommandOutcome:
    """Preconditions shared by CAMP commands that don't require an
    already-joined adventurer (currently just @login): the CAMP deadline
    is evaluated first (which may itself end the CAMP), then run.state
    == CAMP and an open RunCamp for the current floor must both hold.
    """
    await ensure_camp_deadline_evaluated(session, run_id, now=now)

    run = await (get_run_for_update(session, run_id) if lock_run else get_run(session, run_id))
    if run is None or run.state != RunState.CAMP:
        return CommandOutcome(processed=False, reason=NOT_IN_CAMP, result=None)

    camp = await get_open_camp(session, run_id, run.current_floor)
    if camp is None:
        return CommandOutcome(processed=False, reason=NOT_IN_CAMP, result=None)

    return ResolvedCampOnly(run=run, camp=camp)


async def resolve_camp_session(
    session: AsyncSession,
    run_id: uuid.UUID,
    viewer_id: str,
    *,
    now: datetime,
    lock_run: bool = False,
) -> ResolvedCampSession | CommandOutcome:
    """Common preconditions shared by every CAMP command that acts on an
    already-joined adventurer:

    the CAMP deadline is evaluated first, then run.state == CAMP, an
    open RunCamp exists for the current floor, and the viewer maps to a
    currently alive & participating RunAdventurer.

    Returns the resolved rows, or a rejecting CommandOutcome the caller
    should return unchanged.
    """
    resolved = await resolve_camp_only(session, run_id, now=now, lock_run=lock_run)
    if isinstance(resolved, CommandOutcome):
        return resolved
    run, camp = resolved.run, resolved.camp

    adventurer = await get_adventurer_by_viewer(session, run_id, viewer_id)
    if adventurer is None or not adventurer.is_alive or not adventurer.is_participating:
        return CommandOutcome(processed=False, reason=NOT_JOINED, result=None)

    return ResolvedCampSession(run=run, camp=camp, adventurer=adventurer)
