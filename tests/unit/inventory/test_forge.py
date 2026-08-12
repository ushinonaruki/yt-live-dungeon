from yt_live_dungeon.features.inventory.forge import forge


def test_forge_increases_level_for_all_matching_attribute_items(make_entry):
    matching_a = make_entry(slot=1, item_id=1, attribute="RR", current_level=1)
    matching_b = make_entry(slot=2, item_id=2, attribute="RR", current_level=3)

    result = forge(
        [matching_a, matching_b], "RR", hp=500, mp=100, base_max_hp=500, base_max_mp=100
    )

    levels = {e.definition.item_id: e.current_level for e in result.entries}
    assert levels[1] == 2
    assert levels[2] == 4
    assert result.affected_count == 2


def test_forge_leaves_non_matching_attribute_items_unchanged(make_entry):
    matching = make_entry(slot=1, item_id=1, attribute="RR", current_level=1)
    other = make_entry(slot=2, item_id=2, attribute="BB", current_level=1)

    result = forge([matching, other], "RR", hp=500, mp=100, base_max_hp=500, base_max_mp=100)

    levels = {e.definition.item_id: e.current_level for e in result.entries}
    assert levels[1] == 2
    assert levels[2] == 1
    assert result.affected_count == 1


def test_forge_includes_blessing_like_item_in_the_same_matching_pass(make_entry):
    # Blessing items carry no special flag; they are matched purely by
    # `attribute`, the same as any pool item.
    blessing_like = make_entry(slot=1, item_id=1, attribute="RR", current_level=1)

    result = forge([blessing_like], "RR", hp=500, mp=100, base_max_hp=500, base_max_mp=100)

    assert result.entries[0].current_level == 2
    assert result.affected_count == 1


def test_forge_with_zero_matches_succeeds_with_affected_count_zero(make_entry):
    other = make_entry(slot=1, item_id=1, attribute="BB", current_level=1)

    result = forge([other], "RR", hp=500, mp=100, base_max_hp=500, base_max_mp=100)

    assert result.affected_count == 0
    assert result.entries[0].current_level == 1


def test_forge_clamps_current_hp_and_mp_to_new_max(make_entry):
    entry = make_entry(
        slot=1,
        item_id=1,
        attribute="RR",
        current_level=1,
        base_stat_modifiers={},
        per_level_stat_modifiers={"max_hp": -100, "max_mp": -20},
    )

    result = forge([entry], "RR", hp=500, mp=100, base_max_hp=500, base_max_mp=100)

    # level goes 1 -> 2, so max_hp = 500 + (-100*2) = 300, max_mp = 100 + (-20*2) = 60
    assert result.max_hp == 300
    assert result.max_mp == 60
    assert result.hp == 300
    assert result.mp == 60
