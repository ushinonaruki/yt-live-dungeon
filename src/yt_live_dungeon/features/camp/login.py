from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.errors import LoginConfigurationError
from yt_live_dungeon.domain.inventory import InventoryEntry
from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.adventurer.stats import calculate_final_stats
from yt_live_dungeon.features.camp.session import resolve_camp_only
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Login
from yt_live_dungeon.persistence.models import Run, RunAdventurer, RunCampMember
from yt_live_dungeon.persistence.queries.adventurer import (
    get_adventurer_by_viewer,
    list_active_participants,
)
from yt_live_dungeon.persistence.queries.event import append_event
from yt_live_dungeon.persistence.queries.inventory import apply_entries, to_item_definition
from yt_live_dungeon.persistence.queries.item import get_item
from yt_live_dungeon.persistence.queries.spirit import (
    get_spirit,
    list_active_pool_item_ids,
    list_active_spirit_ids,
)

ALREADY_JOINED = "already_joined"
PARTY_FULL = "party_full"
MAX_PARTICIPANTS = 8

# A brand-new adventurer's starting base stats, before any granted items.
NEW_ADVENTURER_BASE_MAX_HP = 500
NEW_ADVENTURER_BASE_MAX_MP = 100


async def handle_login(command: Login, context: CommandContext) -> CommandOutcome:
    """@login only ever creates a brand-new adventurer. A youtube_id that
    has ever had a RunAdventurer row for this run -- currently
    participating, logged out, or dead -- is rejected outright and
    permanently: @logout is a one-way departure from the run, not a
    pause, so there is no "existing adventurer" branch to rejoin
    through."""
    session = context.session
    now = context.command_input.received_at
    viewer_id = context.command_input.viewer_id

    resolved = await resolve_camp_only(session, context.run_id, now=now, lock_run=True)
    if isinstance(resolved, CommandOutcome):
        return resolved
    run, camp = resolved.run, resolved.camp

    existing = await get_adventurer_by_viewer(session, run.id, viewer_id)
    if existing is not None:
        return CommandOutcome(processed=False, reason=ALREADY_JOINED, result=None)

    # Capacity is checked -- and the spirit/item draw happens -- only
    # after the already-exists rejection above, so neither a full camp
    # nor a repeat login ever consumes randomness or writes anything.
    current_participants = await list_active_participants(session, run.id)
    if len(current_participants) >= MAX_PARTICIPANTS:
        return CommandOutcome(processed=False, reason=PARTY_FULL, result=None)

    adventurer, granted = await _onboard_new_adventurer(
        session, run, viewer_id, now, context.random_source
    )

    session.add(
        RunCampMember(
            camp_id=camp.id,
            run_adventurer_id=adventurer.id,
            can_select_action=False,
            selected_action=None,
            selected_at=None,
            ready_at=None,
            left_at=None,
        )
    )

    body = {"adventurer": str(adventurer.id), "spirit": adventurer.spirit_id, **granted}
    await append_event(session, run.id, "adventurer_login", body)

    return CommandOutcome(processed=True, reason=None, result=None)


async def _onboard_new_adventurer(
    session: AsyncSession,
    run: Run,
    viewer_id: str,
    now: datetime,
    random_source: RandomSource,
) -> tuple[RunAdventurer, dict]:
    spirit_ids = await list_active_spirit_ids(session)
    if not spirit_ids:
        raise LoginConfigurationError("no active spirits available")
    spirit_id = random_source.sample(spirit_ids, 1)[0]
    spirit = await get_spirit(session, spirit_id)

    pool_item_ids = await list_active_pool_item_ids(session, spirit.id)
    if not pool_item_ids:
        raise LoginConfigurationError(f"spirit {spirit_id} has no active pool items")
    pool_item_id = random_source.sample(pool_item_ids, 1)[0]

    adventurer = RunAdventurer(
        run_id=run.id,
        youtube_id=viewer_id,
        hp=NEW_ADVENTURER_BASE_MAX_HP,
        mp=NEW_ADVENTURER_BASE_MAX_MP,
        base_max_hp=NEW_ADVENTURER_BASE_MAX_HP,
        base_max_mp=NEW_ADVENTURER_BASE_MAX_MP,
        spirit_id=spirit.id,
        is_alive=True,
        is_participating=True,
    )
    session.add(adventurer)
    await session.flush()

    blessing_item = await get_item(session, spirit.blessing_item_id)
    pool_item = await get_item(session, pool_item_id)
    entries = [
        InventoryEntry(slot=1, current_level=1, definition=to_item_definition(blessing_item)),
        InventoryEntry(slot=2, current_level=1, definition=to_item_definition(pool_item)),
    ]
    await apply_entries(
        session, adventurer.id, [], entries, acquired_floor=run.current_floor, acquired_at=now
    )

    stats = calculate_final_stats(adventurer.base_max_hp, adventurer.base_max_mp, entries)
    adventurer.hp = stats.max_hp
    adventurer.mp = stats.max_mp

    return adventurer, {"blessing_item": blessing_item.id, "pool_item": pool_item.id}
