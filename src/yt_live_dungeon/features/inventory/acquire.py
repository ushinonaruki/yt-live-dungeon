from collections.abc import Sequence
from dataclasses import dataclass, replace

from yt_live_dungeon.domain.inventory import MAX_SLOTS, InventoryEntry, ItemDefinition
from yt_live_dungeon.features.adventurer.stats import calculate_final_stats, clamp_current_vitals


@dataclass(frozen=True)
class AcquireResult:
    success: bool
    entries: tuple[InventoryEntry, ...]
    hp: int
    mp: int
    max_hp: int
    max_mp: int
    reason: str | None = None


def acquire_item(
    entries: Sequence[InventoryEntry],
    item: ItemDefinition,
    *,
    hp: int,
    mp: int,
    base_max_hp: int,
) -> AcquireResult:
    existing = next((e for e in entries if e.definition.item_id == item.item_id), None)

    if existing is not None:
        new_entries = tuple(
            replace(e, current_level=e.current_level + 5) if e is existing else e
            for e in entries
        )
        return _result(new_entries, hp, mp, base_max_hp, success=True)

    if len(entries) >= MAX_SLOTS:
        return _result(
            tuple(entries), hp, mp, base_max_hp, success=False, reason="inventory_full"
        )

    used_slots = {e.slot for e in entries}
    new_slot = next(slot for slot in range(1, MAX_SLOTS + 1) if slot not in used_slots)
    new_entry = InventoryEntry(slot=new_slot, current_level=1, definition=item)
    new_entries = (*tuple(entries), new_entry)
    return _result(new_entries, hp, mp, base_max_hp, success=True)


def _result(
    entries: tuple[InventoryEntry, ...],
    hp: int,
    mp: int,
    base_max_hp: int,
    *,
    success: bool,
    reason: str | None = None,
) -> AcquireResult:
    stats = calculate_final_stats(base_max_hp, entries)
    clamped_hp, clamped_mp = clamp_current_vitals(hp, mp, stats.max_hp)
    return AcquireResult(
        success=success,
        entries=entries,
        hp=clamped_hp,
        mp=clamped_mp,
        max_hp=stats.max_hp,
        max_mp=stats.max_mp,
        reason=reason,
    )
