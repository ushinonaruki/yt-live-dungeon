from yt_live_dungeon.features.inventory.reorder import reorder


def _slots_by_item(entries):
    return {e.definition.item_id: e.slot for e in entries}


def test_reorder_applies_requested_order(make_entry):
    entries = [make_entry(slot=n, item_id=n) for n in range(1, 6)]

    result = reorder(entries, "31425")

    assert result.success is True
    slots = _slots_by_item(result.entries)
    # old 3 -> new 1, old 1 -> new 2, old 4 -> new 3, old 2 -> new 4, old 5 -> new 5
    assert slots[3] == 1
    assert slots[1] == 2
    assert slots[4] == 3
    assert slots[2] == 4
    assert slots[5] == 5


def test_reorder_rejects_duplicate_slot_and_leaves_entries_unchanged(make_entry):
    entries = [make_entry(slot=n, item_id=n) for n in range(1, 4)]

    result = reorder(entries, "121")

    assert result.success is False
    assert result.entries == tuple(entries)


def test_reorder_rejects_missing_slot_and_leaves_entries_unchanged(make_entry):
    entries = [make_entry(slot=n, item_id=n) for n in range(1, 4)]

    result = reorder(entries, "12")

    assert result.success is False
    assert result.entries == tuple(entries)


def test_reorder_rejects_slot_that_does_not_exist_and_leaves_entries_unchanged(make_entry):
    entries = [make_entry(slot=n, item_id=n) for n in range(1, 4)]

    result = reorder(entries, "129")

    assert result.success is False
    assert result.entries == tuple(entries)


def test_reorder_rejects_non_ascii_digits(make_entry):
    entries = [make_entry(slot=n, item_id=n) for n in range(1, 4)]

    result = reorder(entries, "１２３")  # fullwidth 1,2,3

    assert result.success is False
    assert result.entries == tuple(entries)


def test_reorder_rejects_length_mismatch(make_entry):
    entries = [make_entry(slot=n, item_id=n) for n in range(1, 4)]

    result = reorder(entries, "1234")

    assert result.success is False
    assert result.entries == tuple(entries)
