from yt_live_dungeon.features.camp.bag import handle_bag
from yt_live_dungeon.features.camp.move import handle_move
from yt_live_dungeon.features.camp.select_action import handle_select
from yt_live_dungeon.features.camp.spell_detail import handle_spell
from yt_live_dungeon.features.camp.status import handle_status
from yt_live_dungeon.features.commands.dispatch import HandlerRegistry
from yt_live_dungeon.features.commands.parse import Bag, Move, Select, Spell, Status


def build_camp_handlers() -> HandlerRegistry:
    """A fresh handler mapping per call -- never a shared module-global
    registry, so concurrent requests can never see each other's handlers."""
    return {
        Select: handle_select,
        Move: handle_move,
        Status: handle_status,
        Bag: handle_bag,
        Spell: handle_spell,
    }
