import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.inventory import InventoryEntry, ItemDefinition
from yt_live_dungeon.persistence.models import Item, RunAdventurerItem

OwnedRow = tuple[RunAdventurerItem, Item]


async def list_owned_rows(
    session: AsyncSession, run_adventurer_id: uuid.UUID, *, for_update: bool = False
) -> list[OwnedRow]:
    """(RunAdventurerItem, Item) pairs for one adventurer, ordered by slot."""
    stmt = (
        select(RunAdventurerItem, Item)
        .join(Item, Item.id == RunAdventurerItem.item_id)
        .where(RunAdventurerItem.run_adventurer_id == run_adventurer_id)
        .order_by(RunAdventurerItem.slot)
    )
    if for_update:
        stmt = stmt.with_for_update(of=RunAdventurerItem)
    result = await session.execute(stmt)
    return list(result.all())


def to_item_definition(item: Item) -> ItemDefinition:
    return ItemDefinition(
        item_id=item.id,
        attribute=item.attribute,
        granted_spell_id=item.granted_spell_id,
        base_stat_modifiers=item.base_stat_modifiers,
        per_level_stat_modifiers=item.per_level_stat_modifiers,
    )


def to_inventory_entries(rows: list[OwnedRow]) -> list[InventoryEntry]:
    return [
        InventoryEntry(
            slot=row_item.slot,
            current_level=row_item.current_level,
            definition=to_item_definition(item),
        )
        for row_item, item in rows
    ]


async def apply_entries(
    session: AsyncSession,
    run_adventurer_id: uuid.UUID,
    existing_rows: list[RunAdventurerItem],
    entries: list[InventoryEntry],
    *,
    acquired_floor: int,
    acquired_at: datetime,
) -> None:
    """Persist a full desired-state list of InventoryEntry (the output of
    the pure acquire/forge/reorder functions) back to run_adventurer_items.

    All existing rows are deleted and flushed before any are re-inserted,
    so slot reassignment (as in @move) never hits the (adventurer, slot)
    unique constraint mid-update. Rows matched by item_id keep their
    original id/acquired_floor/acquired_at; a row with no match is a new
    acquisition and uses `acquired_floor`/`acquired_at`.
    """
    by_item_id = {row.item_id: row for row in existing_rows}

    for row in existing_rows:
        await session.delete(row)
    if existing_rows:
        await session.flush()

    for entry in entries:
        existing = by_item_id.get(entry.definition.item_id)
        if existing is not None:
            session.add(
                RunAdventurerItem(
                    id=existing.id,
                    run_adventurer_id=run_adventurer_id,
                    item_id=entry.definition.item_id,
                    slot=entry.slot,
                    current_level=entry.current_level,
                    acquired_floor=existing.acquired_floor,
                    acquired_at=existing.acquired_at,
                )
            )
        else:
            session.add(
                RunAdventurerItem(
                    run_adventurer_id=run_adventurer_id,
                    item_id=entry.definition.item_id,
                    slot=entry.slot,
                    current_level=entry.current_level,
                    acquired_floor=acquired_floor,
                    acquired_at=acquired_at,
                )
            )
