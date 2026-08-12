import math
from dataclasses import dataclass

from yt_live_dungeon.domain.attributes import ATTRIBUTE_MODIFIER_KEYS

HP_SCALING_PER_FLOOR = 0.25
ATTRIBUTE_BONUS_PER_FLOOR = 5


@dataclass(frozen=True)
class EnemyFloorStats:
    max_hp: int
    attributes: dict[str, int]


def calculate_enemy_floor_stats(
    base_max_hp: int, base_attributes: dict[str, int], floor: int
) -> EnemyFloorStats:
    """Floor-scaled enemy max HP and 10-attribute values.

    max_hp = floor(base_max_hp * (1 + 0.25 * (floor - 1)))
    attributes[key] = base_attributes[key] + 5 * (floor - 1)

    Participant count is intentionally not a factor here -- the earlier
    per-participant attribute bonus was dropped from the confirmed spec.
    Max MP, MP regen, spell power, MP cost, weak/break/chain are untouched
    by floor scaling and are not computed by this function.
    """
    max_hp = math.floor(base_max_hp * (1 + HP_SCALING_PER_FLOOR * (floor - 1)))
    attributes = {
        key: base_attributes.get(key, 0) + ATTRIBUTE_BONUS_PER_FLOOR * (floor - 1)
        for key in ATTRIBUTE_MODIFIER_KEYS
    }
    return EnemyFloorStats(max_hp=max_hp, attributes=attributes)
