from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.features.adventurer.stats import calculate_final_stats
from yt_live_dungeon.persistence.models import Run, RunAdventurer, RunState
from yt_live_dungeon.persistence.queries.event import append_event
from yt_live_dungeon.persistence.queries.inventory import list_owned_rows, to_inventory_entries


async def start_next_floor(
    session: AsyncSession,
    run: Run,
    participants: list[RunAdventurer],
    *,
    now: datetime,
) -> None:
    """Advances `run` to its next floor for the given, already-resolved
    list of currently participating adventurers: fully heals their
    item-inclusive max MP, leaves HP untouched, and transitions the run
    to BATTLE.

    Never commits/rollbacks -- the caller (features/camp/end.py) owns the
    transaction, having already ended the CAMP within the same one.

    Enemy population for the new floor is intentionally out of scope:
    there is no runtime enemy table yet, and adding one would require a
    migration, which this commit must not do. Nothing about "which
    enemy" is decided or persisted here; that is deferred to whichever
    future commit introduces that schema and the Battle Engine.

    Can raise InvalidStatModifierError (from calculate_final_stats) if a
    participant's owned item has malformed stat modifiers -- since this
    runs in the same transaction as the CAMP-ending mutations already
    made by the caller, that failure rolls back the whole transaction,
    so the CAMP never ends up marked ended without a floor transition.
    """
    for adventurer in participants:
        rows = await list_owned_rows(session, adventurer.id)
        entries = to_inventory_entries(rows)
        stats = calculate_final_stats(adventurer.base_max_hp, adventurer.base_max_mp, entries)
        adventurer.mp = stats.max_mp

    run.current_floor += 1
    run.state = RunState.BATTLE

    await append_event(session, run.id, "floor_started", {"floor": run.current_floor})
