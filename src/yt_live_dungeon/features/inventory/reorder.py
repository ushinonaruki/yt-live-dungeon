from collections.abc import Sequence
from dataclasses import dataclass, replace

from yt_live_dungeon.domain.inventory import InventoryEntry


@dataclass(frozen=True)
class ReorderResult:
    success: bool
    entries: tuple[InventoryEntry, ...]
    reason: str | None = None


def reorder(entries: Sequence[InventoryEntry], order: str) -> ReorderResult:
    original = tuple(entries)

    if not order.isascii() or not order.isdigit():
        return ReorderResult(success=False, entries=original, reason="invalid_syntax")

    if len(order) != len(original):
        return ReorderResult(success=False, entries=original, reason="invalid_syntax")

    requested_slots = [int(digit) for digit in order]

    if len(set(requested_slots)) != len(requested_slots):
        return ReorderResult(success=False, entries=original, reason="invalid_syntax")

    current_slots = {e.slot for e in original}
    if set(requested_slots) != current_slots:
        return ReorderResult(success=False, entries=original, reason="invalid_syntax")

    by_slot = {e.slot: e for e in original}
    reordered = tuple(
        replace(by_slot[old_slot], slot=new_slot)
        for new_slot, old_slot in enumerate(requested_slots, start=1)
    )
    return ReorderResult(success=True, entries=reordered)
