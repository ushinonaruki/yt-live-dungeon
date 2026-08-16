from yt_live_dungeon.features.adventurer.stats import calculate_final_stats
from yt_live_dungeon.features.camp.session import resolve_camp_session
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Status
from yt_live_dungeon.persistence.queries.camp import get_camp_member
from yt_live_dungeon.persistence.queries.inventory import list_owned_rows, to_inventory_entries
from yt_live_dungeon.persistence.queries.spirit import get_spirit


async def handle_status(command: Status, context: CommandContext) -> CommandOutcome:
    session = context.session
    resolved = await resolve_camp_session(
        session,
        context.run_id,
        context.command_input.viewer_id,
        now=context.command_input.received_at,
        random_source=context.random_source,
    )
    if isinstance(resolved, CommandOutcome):
        return resolved
    camp, adventurer = resolved.camp, resolved.adventurer

    rows = await list_owned_rows(session, adventurer.id)
    entries = to_inventory_entries(rows)
    stats = calculate_final_stats(adventurer.base_max_hp, entries)

    member = await get_camp_member(session, camp.id, adventurer.id)
    is_ready = member is not None and member.ready_at is not None

    spirit = await get_spirit(session, adventurer.spirit_id) if adventurer.spirit_id else None

    result = {
        "run_adventurer_id": str(adventurer.id),
        "hp": adventurer.hp,
        "max_hp": stats.max_hp,
        "mp": adventurer.mp,
        "max_mp": stats.max_mp,
        "attributes": stats.attributes,
        "spirit": (
            {"id": spirit.id, "display_name": spirit.display_name} if spirit is not None else None
        ),
        "is_ready": is_ready,
    }

    return CommandOutcome(processed=True, reason=None, result=result)
