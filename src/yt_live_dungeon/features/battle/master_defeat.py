from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.errors import CampConfigurationError
from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.camp.start import start_camp
from yt_live_dungeon.features.floor.start import LAST_FLOOR
from yt_live_dungeon.persistence.models import Run, RunEnemy, RunState
from yt_live_dungeon.persistence.queries.egregore import list_active_egregore_ids
from yt_live_dungeon.persistence.queries.event import append_event


async def check_and_handle_master_defeat(
    session: AsyncSession,
    run: Run,
    *,
    now: datetime,
    random_source: RandomSource,
) -> None:
    """If the current floor's master RunEnemy is defeated, breaks
    through the floor: starts CAMP (any floor before 100) or ends the
    run at its final result (floor 100). Surviving minions never block
    this, and defeating only minions never triggers it -- this function
    looks at the master's own defeated_at, nothing else.

    Idempotent and safe under concurrent/duplicate calls: it only acts
    while run.state == BATTLE, and both branches move the run out of
    BATTLE as their first mutation. Assumes the caller already holds a
    FOR UPDATE lock on `run` (the established convention for anything
    that may transition run.state). Never commits/rollbacks.

    This is the shared, reusable master-defeat trigger for *any* Use
    Case that may reduce the master's HP to 0 -- not specific to enemy-
    initiated actions. Commit 7 only wires an enemy-decision path into
    it (features/battle/resolve.py); an adventurer-attack path is not
    part of this commit and would call this same function once built.
    """
    if run.state != RunState.BATTLE:
        return

    master = (
        await session.execute(
            select(RunEnemy).where(
                RunEnemy.run_id == run.id,
                RunEnemy.floor == run.current_floor,
                RunEnemy.role == "master",
            )
        )
    ).scalar_one_or_none()
    if master is None or master.defeated_at is None:
        return

    if run.current_floor >= LAST_FLOOR:
        run.state = RunState.GAME_OVER
        run.ended_at = now
        await append_event(session, run.id, "run_completed", {"floor": run.current_floor})
        return

    egregore_ids = await list_active_egregore_ids(session)
    if not egregore_ids:
        raise CampConfigurationError("no active egregores available to start CAMP")
    egregore_id = random_source.sample(egregore_ids, 1)[0]

    await start_camp(session, run.id, egregore_id, now=now, random_source=random_source)
