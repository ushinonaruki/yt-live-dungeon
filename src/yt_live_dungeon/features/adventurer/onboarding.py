from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.errors import LoginConfigurationError
from yt_live_dungeon.domain.inventory import InventoryEntry
from yt_live_dungeon.domain.mp_regen import MAX_MP
from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.adventurer.stats import calculate_final_stats
from yt_live_dungeon.persistence.models import Run, RunAdventurer
from yt_live_dungeon.persistence.queries.egregore import (
    get_egregore,
    list_active_egregore_ids,
    list_active_pool_item_ids,
)
from yt_live_dungeon.persistence.queries.inventory import apply_entries, to_item_definition
from yt_live_dungeon.persistence.queries.item import get_item

# A brand-new adventurer's starting base HP, before any granted items.
# Max MP has no equivalent "base" constant of its own -- it is always
# the single fixed MAX_MP (see domain/mp_regen.py).
NEW_ADVENTURER_BASE_MAX_HP = 500


async def onboard_new_adventurer(
    session: AsyncSession,
    run: Run,
    viewer_id: str,
    now: datetime,
    random_source: RandomSource,
) -> tuple[RunAdventurer, dict]:
    """Creates and fully equips a brand-new RunAdventurer: draws a random
    active egregore, grants its blessing item plus one random active pool
    item, and sets hp/mp to the resulting max.

    Shared by every Use Case that onboards a first-time participant into
    a run -- CAMP's @login (features/camp/login.py) and WAITING's @login
    (features/waiting/login.py) alike -- so the onboarding rules (egregore/
    item draw order, starting stats, granted-item bookkeeping) are
    defined once. Callers own capacity/duplicate-participant checks and
    any membership row of their own (e.g. RunCampMember); this only adds
    the RunAdventurer row and its granted items, and flushes.
    """
    egregore_ids = await list_active_egregore_ids(session)
    if not egregore_ids:
        raise LoginConfigurationError("no active egregores available")
    egregore_id = random_source.sample(egregore_ids, 1)[0]
    egregore = await get_egregore(session, egregore_id)

    pool_item_ids = await list_active_pool_item_ids(session, egregore.id)
    if not pool_item_ids:
        raise LoginConfigurationError(f"egregore {egregore_id} has no active pool items")
    pool_item_id = random_source.sample(pool_item_ids, 1)[0]

    adventurer = RunAdventurer(
        run_id=run.id,
        youtube_id=viewer_id,
        hp=NEW_ADVENTURER_BASE_MAX_HP,
        mp=MAX_MP,
        base_max_hp=NEW_ADVENTURER_BASE_MAX_HP,
        base_max_mp=MAX_MP,
        egregore_id=egregore.id,
        is_alive=True,
        is_participating=True,
    )
    session.add(adventurer)
    await session.flush()

    blessing_item = await get_item(session, egregore.blessing_item_id)
    pool_item = await get_item(session, pool_item_id)
    entries = [
        InventoryEntry(slot=1, current_level=1, definition=to_item_definition(blessing_item)),
        InventoryEntry(slot=2, current_level=1, definition=to_item_definition(pool_item)),
    ]
    await apply_entries(
        session, adventurer.id, [], entries, acquired_floor=run.current_floor, acquired_at=now
    )

    stats = calculate_final_stats(adventurer.base_max_hp, entries)
    adventurer.hp = stats.max_hp
    adventurer.mp = stats.max_mp

    return adventurer, {"blessing_item": blessing_item.id, "pool_item": pool_item.id}
