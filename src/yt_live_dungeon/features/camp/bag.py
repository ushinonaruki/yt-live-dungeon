from yt_live_dungeon.features.adventurer.stats import item_modifiers
from yt_live_dungeon.features.camp.session import resolve_camp_session
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Bag
from yt_live_dungeon.persistence.queries.inventory import list_owned_rows, to_inventory_entries
from yt_live_dungeon.persistence.queries.spell import get_spell


async def handle_bag(command: Bag, context: CommandContext) -> CommandOutcome:
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
    adventurer = resolved.adventurer

    rows = await list_owned_rows(session, adventurer.id)
    entries = to_inventory_entries(rows)

    items = []
    for (_row, item), entry in zip(rows, entries, strict=True):
        spell = await get_spell(session, item.granted_spell_id)
        items.append(
            {
                "slot": entry.slot,
                "item_id": item.id,
                "display_name": item.display_name,
                "attribute": item.attribute,
                "current_level": entry.current_level,
                "final_modifiers": item_modifiers(entry),
                "spell": {
                    "id": spell.id,
                    "command": spell.command,
                    "display_name": spell.display_name,
                    "attribute": spell.attribute,
                    "mp_cost": spell.mp_cost,
                    "target_rule": spell.target_rule,
                    "effects": spell.effects,
                },
            }
        )

    return CommandOutcome(processed=True, reason=None, result={"items": items})
