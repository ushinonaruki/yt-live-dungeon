from collections.abc import Iterable
from dataclasses import dataclass

from yt_live_dungeon.domain.attributes import ATTRIBUTE_MODIFIER_KEYS, STAT_MODIFIER_KEYS
from yt_live_dungeon.domain.errors import InvalidStatModifierError
from yt_live_dungeon.domain.inventory import InventoryEntry


@dataclass(frozen=True)
class FinalStats:
    max_hp: int
    max_mp: int
    attributes: dict[str, int]


def calculate_final_stats(
    base_max_hp: int, base_max_mp: int, entries: Iterable[InventoryEntry]
) -> FinalStats:
    totals = dict.fromkeys(STAT_MODIFIER_KEYS, 0)

    for entry in entries:
        definition = entry.definition
        _validate_stat_modifiers(definition.base_stat_modifiers)
        _validate_stat_modifiers(definition.per_level_stat_modifiers)

        for key in STAT_MODIFIER_KEYS:
            base = definition.base_stat_modifiers.get(key, 0)
            per_level = definition.per_level_stat_modifiers.get(key, 0)
            totals[key] += base + per_level * entry.current_level

    return FinalStats(
        max_hp=base_max_hp + totals["max_hp"],
        max_mp=base_max_mp + totals["max_mp"],
        attributes={key: totals[key] for key in ATTRIBUTE_MODIFIER_KEYS},
    )


def usable_spell_ids(entries: Iterable[InventoryEntry]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for entry in entries:
        spell_id = entry.definition.granted_spell_id
        if spell_id not in seen:
            seen.add(spell_id)
            ordered.append(spell_id)
    return ordered


def clamp_current_vitals(hp: int, mp: int, max_hp: int, max_mp: int) -> tuple[int, int]:
    return min(hp, max_hp), min(mp, max_mp)


def _validate_stat_modifiers(modifiers: dict) -> None:
    if not isinstance(modifiers, dict):
        raise InvalidStatModifierError("stat modifiers must be a mapping")
    for key, value in modifiers.items():
        if key not in STAT_MODIFIER_KEYS:
            raise InvalidStatModifierError(f"unknown stat modifier key: {key!r}")
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidStatModifierError(
                f"stat modifier value must be an int: {key!r}={value!r}"
            )
