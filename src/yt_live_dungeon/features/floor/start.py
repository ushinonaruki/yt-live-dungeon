from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.errors import EnemyGroupConfigurationError
from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.adventurer.stats import calculate_final_stats
from yt_live_dungeon.features.floor.group_draw import draw_group_id
from yt_live_dungeon.features.floor.spawn import spawn_group
from yt_live_dungeon.persistence.models import Run, RunAdventurer, RunState
from yt_live_dungeon.persistence.queries.enemy_group import list_active_group_ids
from yt_live_dungeon.persistence.queries.event import append_event
from yt_live_dungeon.persistence.queries.inventory import list_owned_rows, to_inventory_entries

LAST_FLOOR = 100


async def start_next_floor(
    session: AsyncSession,
    run: Run,
    participants: list[RunAdventurer],
    *,
    now: datetime,
    random_source: RandomSource,
) -> None:
    """Advances `run` to its next floor for the given, already-resolved
    list of currently participating adventurers.

    Consumes `run.next_group_id` as the new floor's group -- this never
    draws a group for the floor it is starting; that group was already
    decided (and persisted) ahead of time. It then draws and saves a new
    next_group_id for the floor after that, unless the floor just
    started is 100 (there is no floor 101 to hold a next group for).

    Also fully heals participants' item-inclusive max MP, leaves HP
    untouched, and transitions the run to BATTLE.

    Never commits/rollbacks -- the caller (features/camp/end.py) owns the
    transaction, having already ended the CAMP within the same one.

    Raises EnemyGroupConfigurationError if next_group_id is unset (should
    never happen for a run that went through start_run()/a prior
    start_next_floor() call) or if no active group exists to draw the
    *next* next_group from. Can also raise InvalidStatModifierError (from
    calculate_final_stats) if a participant's owned item has malformed
    stat modifiers. Either failure propagates before run.current_floor or
    run.state are touched, so the whole transaction rolls back cleanly.
    """
    if run.next_group_id is None:
        raise EnemyGroupConfigurationError(
            f"run {run.id} has no saved next_group_id to consume"
        )

    next_floor = run.current_floor + 1
    group_id_to_spawn = run.next_group_id

    await spawn_group(session, run.id, next_floor, group_id_to_spawn, now=now)

    for adventurer in participants:
        rows = await list_owned_rows(session, adventurer.id)
        entries = to_inventory_entries(rows)
        stats = calculate_final_stats(adventurer.base_max_hp, adventurer.base_max_mp, entries)
        adventurer.mp = stats.max_mp

    run.current_floor = next_floor
    run.state = RunState.BATTLE

    if next_floor < LAST_FLOOR:
        group_ids = await list_active_group_ids(session)
        if not group_ids:
            raise EnemyGroupConfigurationError("no active enemy groups available")
        run.next_group_id = draw_group_id(group_ids, random_source)
    else:
        run.next_group_id = None

    await append_event(session, run.id, "floor_started", {"floor": next_floor})
