from yt_live_dungeon.features.adventurer.stats import usable_spell_ids
from yt_live_dungeon.features.camp.session import resolve_camp_session
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Spell
from yt_live_dungeon.persistence.queries.inventory import list_owned_rows, to_inventory_entries
from yt_live_dungeon.persistence.queries.spell import get_active_spell_by_command

UNKNOWN_SPELL = "unknown_spell"
SPELL_NOT_UNLOCKED = "spell_not_unlocked"


async def handle_spell(command: Spell, context: CommandContext) -> CommandOutcome:
    session = context.session
    resolved = await resolve_camp_session(
        session, context.run_id, context.command_input.viewer_id
    )
    if isinstance(resolved, CommandOutcome):
        return resolved
    adventurer = resolved.adventurer

    spell = await get_active_spell_by_command(session, command.command)
    if spell is None:
        return CommandOutcome(processed=False, reason=UNKNOWN_SPELL, result=None)

    rows = await list_owned_rows(session, adventurer.id)
    entries = to_inventory_entries(rows)
    unlocked_spell_ids = set(usable_spell_ids(entries))

    if spell.id not in unlocked_spell_ids:
        return CommandOutcome(processed=False, reason=SPELL_NOT_UNLOCKED, result=None)

    result = {
        "id": spell.id,
        "command": spell.command,
        "display_name": spell.display_name,
        "attribute": spell.attribute,
        "mp_cost": spell.mp_cost,
        "target_rule": spell.target_rule,
        "effects": spell.effects,
    }

    return CommandOutcome(processed=True, reason=None, result=result)
