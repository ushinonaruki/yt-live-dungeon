from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.features.adventurer.stats import calculate_final_stats
from yt_live_dungeon.features.camp.session import resolve_camp_session
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Select
from yt_live_dungeon.features.inventory.acquire import acquire_item
from yt_live_dungeon.features.inventory.forge import forge
from yt_live_dungeon.persistence.models import Run, RunAdventurer, RunCamp, RunCampMember
from yt_live_dungeon.persistence.queries.camp import get_camp_member
from yt_live_dungeon.persistence.queries.egregore import get_egregore
from yt_live_dungeon.persistence.queries.event import append_event
from yt_live_dungeon.persistence.queries.inventory import (
    apply_entries,
    list_owned_rows,
    to_inventory_entries,
    to_item_definition,
)
from yt_live_dungeon.persistence.queries.item import get_item

ACTION_NOT_AVAILABLE = "action_not_available"
ACTION_ALREADY_SELECTED = "action_already_selected"
REST_HP_GAIN = 100


async def handle_select(command: Select, context: CommandContext) -> CommandOutcome:
    session = context.session
    resolved = await resolve_camp_session(
        session,
        context.run_id,
        context.command_input.viewer_id,
        now=context.command_input.received_at,
        random_source=context.random_source,
        lock_run=True,
    )
    if isinstance(resolved, CommandOutcome):
        return resolved
    run, camp, adventurer = resolved.run, resolved.camp, resolved.adventurer

    member = await get_camp_member(session, camp.id, adventurer.id)
    if member is None or not member.can_select_action:
        return CommandOutcome(processed=False, reason=ACTION_NOT_AVAILABLE, result=None)
    if member.selected_action is not None:
        return CommandOutcome(processed=False, reason=ACTION_ALREADY_SELECTED, result=None)

    received_at = context.command_input.received_at

    if command.value == 1:
        return await _rest(session, run, adventurer, member, received_at)
    if command.value in (2, 3):
        item_id = camp.candidate_a_item_id if command.value == 2 else camp.candidate_b_item_id
        action_name = "candidate_a" if command.value == 2 else "candidate_b"
        return await _acquire_candidate(
            session, run, adventurer, member, item_id, action_name, received_at
        )
    return await _forge_matching_items(session, run, camp, adventurer, member, received_at)


async def _rest(
    session: AsyncSession,
    run: Run,
    adventurer: RunAdventurer,
    member: RunCampMember,
    received_at: datetime,
) -> CommandOutcome:
    rows = await list_owned_rows(session, adventurer.id)
    entries = to_inventory_entries(rows)
    stats = calculate_final_stats(adventurer.base_max_hp, entries)

    adventurer.hp = min(stats.max_hp, adventurer.hp + REST_HP_GAIN)

    member.selected_action = "rest"
    member.selected_at = received_at

    await append_event(
        session,
        run.id,
        "camp_action_selected",
        {"adventurer": str(adventurer.id), "action": "rest"},
    )

    return CommandOutcome(processed=True, reason=None, result=None)


async def _acquire_candidate(
    session: AsyncSession,
    run: Run,
    adventurer: RunAdventurer,
    member: RunCampMember,
    item_id: int,
    action_name: str,
    received_at: datetime,
) -> CommandOutcome:
    rows = await list_owned_rows(session, adventurer.id, for_update=True)
    entries = to_inventory_entries(rows)

    item = await get_item(session, item_id)
    definition = to_item_definition(item)

    level_before = next(
        (entry.current_level for entry in entries if entry.definition.item_id == item_id),
        None,
    )

    result = acquire_item(
        entries,
        definition,
        hp=adventurer.hp,
        mp=adventurer.mp,
        base_max_hp=adventurer.base_max_hp,
    )

    if not result.success:
        await append_event(
            session,
            run.id,
            "camp_action_failed",
            {"adventurer": str(adventurer.id), "action": action_name, "reason": result.reason},
        )
        return CommandOutcome(processed=False, reason=result.reason, result=None)

    await apply_entries(
        session,
        adventurer.id,
        [row for row, _item in rows],
        list(result.entries),
        acquired_floor=run.current_floor,
        acquired_at=received_at,
    )
    adventurer.hp = result.hp
    adventurer.mp = result.mp

    member.selected_action = action_name
    member.selected_at = received_at

    level_after = next(
        entry.current_level for entry in result.entries if entry.definition.item_id == item_id
    )

    await append_event(
        session,
        run.id,
        "camp_action_selected",
        {
            "adventurer": str(adventurer.id),
            "action": action_name,
            "item": item_id,
            "level_before": level_before,
            "level_after": level_after,
        },
    )

    return CommandOutcome(processed=True, reason=None, result=None)


async def _forge_matching_items(
    session: AsyncSession,
    run: Run,
    camp: RunCamp,
    adventurer: RunAdventurer,
    member: RunCampMember,
    received_at: datetime,
) -> CommandOutcome:
    egregore = await get_egregore(session, camp.egregore_id)

    rows = await list_owned_rows(session, adventurer.id, for_update=True)
    entries = to_inventory_entries(rows)

    result = forge(
        entries,
        egregore.representative_attribute,
        hp=adventurer.hp,
        mp=adventurer.mp,
        base_max_hp=adventurer.base_max_hp,
    )

    await apply_entries(
        session,
        adventurer.id,
        [row for row, _item in rows],
        list(result.entries),
        acquired_floor=run.current_floor,
        acquired_at=received_at,
    )
    adventurer.hp = result.hp
    adventurer.mp = result.mp

    member.selected_action = "forge"
    member.selected_at = received_at

    await append_event(
        session,
        run.id,
        "camp_action_selected",
        {
            "adventurer": str(adventurer.id),
            "action": "forge",
            "affected_count": result.affected_count,
        },
    )

    return CommandOutcome(processed=True, reason=None, result=None)
