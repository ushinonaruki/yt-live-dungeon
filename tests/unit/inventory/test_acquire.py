from yt_live_dungeon.features.inventory.acquire import acquire_item


def test_new_acquisition_starts_at_level_1(make_entry, make_item_definition):
    existing = [make_entry(slot=1, item_id=1)]
    new_item = make_item_definition(item_id=2)

    result = acquire_item(existing, new_item, hp=500, mp=100, base_max_hp=500, base_max_mp=100)

    assert result.success is True
    acquired = next(e for e in result.entries if e.definition.item_id == 2)
    assert acquired.current_level == 1


def test_new_acquisition_uses_smallest_free_slot(make_entry, make_item_definition):
    existing = [make_entry(slot=1, item_id=1), make_entry(slot=3, item_id=3)]
    new_item = make_item_definition(item_id=2)

    result = acquire_item(existing, new_item, hp=500, mp=100, base_max_hp=500, base_max_mp=100)

    acquired = next(e for e in result.entries if e.definition.item_id == 2)
    assert acquired.slot == 2


def test_duplicate_acquisition_increases_level_by_five_without_new_slot(make_entry):
    existing_entry = make_entry(slot=1, item_id=1, current_level=1)
    duplicate_item = existing_entry.definition

    result = acquire_item(
        [existing_entry], duplicate_item, hp=500, mp=100, base_max_hp=500, base_max_mp=100
    )

    assert result.success is True
    assert len(result.entries) == 1
    assert result.entries[0].current_level == 6


def test_unowned_item_rejected_when_inventory_full(make_entry, make_item_definition):
    full_inventory = [make_entry(slot=slot, item_id=slot) for slot in range(1, 9)]
    new_item = make_item_definition(item_id=999)

    result = acquire_item(
        full_inventory, new_item, hp=500, mp=100, base_max_hp=500, base_max_mp=100
    )

    assert result.success is False
    assert result.reason == "inventory_full"
    assert result.entries == tuple(full_inventory)


def test_duplicate_acquisition_succeeds_even_when_inventory_full(make_entry):
    full_inventory = [make_entry(slot=slot, item_id=slot, current_level=1) for slot in range(1, 9)]
    duplicate_item = full_inventory[0].definition

    result = acquire_item(
        full_inventory, duplicate_item, hp=500, mp=100, base_max_hp=500, base_max_mp=100
    )

    assert result.success is True
    assert len(result.entries) == 8
    assert result.entries[0].current_level == 6


def test_acquisition_clamps_current_hp_and_mp_to_new_max(make_entry, make_item_definition):
    existing = []
    shrinking_item = make_item_definition(
        item_id=1,
        base_stat_modifiers={"max_hp": -450, "max_mp": -90},
        per_level_stat_modifiers={},
    )

    result = acquire_item(
        existing, shrinking_item, hp=500, mp=100, base_max_hp=500, base_max_mp=100
    )

    assert result.max_hp == 50
    assert result.max_mp == 10
    assert result.hp == 50
    assert result.mp == 10


def test_acquisition_does_not_heal_current_hp_and_mp_when_max_increases(
    make_entry, make_item_definition
):
    existing = []
    growing_item = make_item_definition(
        item_id=1,
        base_stat_modifiers={"max_hp": 100, "max_mp": 50},
        per_level_stat_modifiers={},
    )

    result = acquire_item(
        existing, growing_item, hp=200, mp=20, base_max_hp=500, base_max_mp=100
    )

    assert result.max_hp == 600
    assert result.max_mp == 150
    assert result.hp == 200
    assert result.mp == 20
