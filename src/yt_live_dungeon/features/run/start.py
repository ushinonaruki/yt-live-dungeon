from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.errors import EnemyGroupConfigurationError
from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.floor.group_draw import draw_group_id
from yt_live_dungeon.features.floor.spawn import spawn_group
from yt_live_dungeon.persistence.models import Run, RunState
from yt_live_dungeon.persistence.queries.enemy_group import list_active_group_ids
from yt_live_dungeon.persistence.queries.event import append_event

FIRST_FLOOR = 1


async def start_run(
    session: AsyncSession, run: Run, *, now: datetime, random_source: RandomSource
) -> None:
    """Initializes a WAITING run's first floor: draws floor 1's group,
    spawns it via the same expansion logic start_next_floor() reuses,
    draws and saves floor 2's next group, and transitions the run to
    BATTLE at floor 1.

    Never commits/rollbacks -- the caller owns the transaction.

    Raises EnemyGroupConfigurationError before any mutation if there are
    no active enemy groups to draw from.
    """
    group_ids = await list_active_group_ids(session)
    if not group_ids:
        raise EnemyGroupConfigurationError("no active enemy groups available")

    current_group_id = draw_group_id(group_ids, random_source)
    await spawn_group(session, run.id, FIRST_FLOOR, current_group_id, now=now)

    run.next_group_id = draw_group_id(group_ids, random_source)
    run.current_floor = FIRST_FLOOR
    run.state = RunState.BATTLE

    await append_event(session, run.id, "floor_started", {"floor": FIRST_FLOOR})
