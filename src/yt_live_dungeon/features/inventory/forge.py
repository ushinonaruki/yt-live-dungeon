from collections.abc import Sequence
from dataclasses import dataclass, replace

from yt_live_dungeon.domain.inventory import InventoryEntry
from yt_live_dungeon.features.adventurer.stats import calculate_final_stats, clamp_current_vitals


@dataclass(frozen=True)
class ForgeResult:
    entries: tuple[InventoryEntry, ...]
    affected_count: int
    hp: int
    mp: int
    max_hp: int
    max_mp: int


def forge(
    entries: Sequence[InventoryEntry],
    attribute: str,
    *,
    hp: int,
    mp: int,
    base_max_hp: int,
    base_max_mp: int,
) -> ForgeResult:
    new_entries = tuple(
        replace(e, current_level=e.current_level + 1) if e.definition.attribute == attribute else e
        for e in entries
    )
    affected_count = sum(1 for e in entries if e.definition.attribute == attribute)

    stats = calculate_final_stats(base_max_hp, base_max_mp, new_entries)
    clamped_hp, clamped_mp = clamp_current_vitals(hp, mp, stats.max_hp, stats.max_mp)

    return ForgeResult(
        entries=new_entries,
        affected_count=affected_count,
        hp=clamped_hp,
        mp=clamped_mp,
        max_hp=stats.max_hp,
        max_mp=stats.max_mp,
    )
