import pytest

from yt_live_dungeon.domain.inventory import InventoryEntry, ItemDefinition


@pytest.fixture
def make_item_definition():
    def _make(
        item_id: int,
        attribute: str = "RR",
        granted_spell_id: int = 1,
        base_stat_modifiers: dict | None = None,
        per_level_stat_modifiers: dict | None = None,
    ) -> ItemDefinition:
        return ItemDefinition(
            item_id=item_id,
            attribute=attribute,
            granted_spell_id=granted_spell_id,
            base_stat_modifiers=base_stat_modifiers or {},
            per_level_stat_modifiers=per_level_stat_modifiers or {},
        )

    return _make


@pytest.fixture
def make_entry(make_item_definition):
    def _make(
        slot: int,
        current_level: int = 1,
        item_id: int | None = None,
        **item_kwargs,
    ) -> InventoryEntry:
        definition = make_item_definition(
            item_id=item_id if item_id is not None else slot, **item_kwargs
        )
        return InventoryEntry(slot=slot, current_level=current_level, definition=definition)

    return _make
