from yt_live_dungeon.features.camp.session import resolve_camp_session
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Move
from yt_live_dungeon.features.inventory.reorder import reorder
from yt_live_dungeon.persistence.queries.event import append_event
from yt_live_dungeon.persistence.queries.inventory import (
    apply_entries,
    list_owned_rows,
    to_inventory_entries,
)


async def handle_move(command: Move, context: CommandContext) -> CommandOutcome:
    session = context.session
    resolved = await resolve_camp_session(
        session, context.run_id, context.command_input.viewer_id
    )
    if isinstance(resolved, CommandOutcome):
        return resolved
    run, _camp, adventurer = resolved.run, resolved.camp, resolved.adventurer

    rows = await list_owned_rows(session, adventurer.id, for_update=True)
    entries = to_inventory_entries(rows)

    result = reorder(entries, command.order)
    if not result.success:
        return CommandOutcome(processed=False, reason=result.reason, result=None)

    old_order = "".join(str(entry.slot) for entry in entries)

    await apply_entries(
        session,
        adventurer.id,
        [row for row, _item in rows],
        list(result.entries),
        acquired_floor=run.current_floor,
        acquired_at=context.command_input.received_at,
    )

    await append_event(
        session,
        run.id,
        "inventory_moved",
        {"adventurer": str(adventurer.id), "old_order": old_order, "new_order": command.order},
    )

    return CommandOutcome(processed=True, reason=None, result=None)
