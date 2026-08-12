import pytest

from yt_live_dungeon.domain.errors import InvalidStatModifierError
from yt_live_dungeon.features.adventurer.stats import (
    calculate_final_stats,
    clamp_current_vitals,
    usable_spell_ids,
)


def test_level_1_uses_base_plus_per_level_times_one(make_entry):
    entry = make_entry(
        slot=1,
        current_level=1,
        base_stat_modifiers={"max_hp": 10, "rr": 2},
        per_level_stat_modifiers={"max_hp": 5, "rr": 1},
    )

    stats = calculate_final_stats(base_max_hp=500, base_max_mp=100, entries=[entry])

    assert stats.max_hp == 500 + (10 + 5 * 1)
    assert stats.attributes["rr"] == 2 + 1 * 1


def test_negative_modifiers_are_summed_correctly(make_entry):
    entry = make_entry(
        slot=1,
        current_level=2,
        base_stat_modifiers={"max_hp": -20, "rr": -3},
        per_level_stat_modifiers={"max_hp": -5, "rr": -1},
    )

    stats = calculate_final_stats(base_max_hp=500, base_max_mp=100, entries=[entry])

    assert stats.max_hp == 500 + (-20 + -5 * 2)
    assert stats.attributes["rr"] == -3 + -1 * 2


def test_multiple_items_sum_max_hp_max_mp_and_all_ten_attributes(make_entry):
    entry_a = make_entry(
        slot=1,
        current_level=1,
        base_stat_modifiers={"max_hp": 50, "max_mp": 20, "rr": 10, "bb": 5},
        per_level_stat_modifiers={"max_hp": 5, "rr": 1},
    )
    entry_b = make_entry(
        slot=2,
        current_level=3,
        base_stat_modifiers={"max_mp": 10, "bb": 3, "yr": 4},
        per_level_stat_modifiers={"max_mp": 2, "bb": 1},
    )

    stats = calculate_final_stats(base_max_hp=500, base_max_mp=100, entries=[entry_a, entry_b])

    assert stats.max_hp == 500 + (50 + 5 * 1)
    assert stats.max_mp == 100 + (20) + (10 + 2 * 3)
    assert stats.attributes["rr"] == 10 + 1 * 1
    assert stats.attributes["bb"] == 5 + (3 + 1 * 3)
    assert stats.attributes["yr"] == 4
    for key in ("yy", "gy", "gg", "bg", "pb", "pp", "rp"):
        assert stats.attributes[key] == 0


def test_blessing_like_item_uses_the_same_aggregation_as_any_other_item(make_entry):
    # ItemDefinition has no "is_blessing" flag; a blessing item is just an
    # item with a fixed attribute bonus, aggregated through the same path.
    blessing_entry = make_entry(
        slot=1,
        current_level=1,
        base_stat_modifiers={"max_hp": 50, "rr": 10},
        per_level_stat_modifiers={"max_hp": 5, "rr": 1},
    )
    pool_entry = make_entry(
        slot=2,
        current_level=1,
        base_stat_modifiers={"rr": 5},
        per_level_stat_modifiers={"rr": 1},
    )

    stats = calculate_final_stats(
        base_max_hp=500, base_max_mp=100, entries=[blessing_entry, pool_entry]
    )

    assert stats.max_hp == 500 + (50 + 5)
    assert stats.attributes["rr"] == (10 + 1) + (5 + 1)


def test_rejects_unknown_stat_modifier_key(make_entry):
    entry = make_entry(slot=1, base_stat_modifiers={"strength": 1})

    with pytest.raises(InvalidStatModifierError):
        calculate_final_stats(base_max_hp=500, base_max_mp=100, entries=[entry])


def test_rejects_non_integer_stat_modifier_value(make_entry):
    entry = make_entry(slot=1, base_stat_modifiers={"max_hp": 1.5})

    with pytest.raises(InvalidStatModifierError):
        calculate_final_stats(base_max_hp=500, base_max_mp=100, entries=[entry])


def test_rejects_bool_stat_modifier_value(make_entry):
    entry = make_entry(slot=1, base_stat_modifiers={"max_hp": True})

    with pytest.raises(InvalidStatModifierError):
        calculate_final_stats(base_max_hp=500, base_max_mp=100, entries=[entry])


def test_rejects_nested_stat_modifier_value(make_entry):
    entry = make_entry(slot=1, base_stat_modifiers={"max_hp": {"nested": 1}})

    with pytest.raises(InvalidStatModifierError):
        calculate_final_stats(base_max_hp=500, base_max_mp=100, entries=[entry])


def test_does_not_clamp_max_hp_or_attributes_to_any_lower_bound(make_entry):
    entry = make_entry(
        slot=1,
        current_level=1,
        base_stat_modifiers={"max_hp": -10_000, "rr": -500},
        per_level_stat_modifiers={},
    )

    stats = calculate_final_stats(base_max_hp=500, base_max_mp=100, entries=[entry])

    assert stats.max_hp == 500 - 10_000
    assert stats.attributes["rr"] == -500


def test_usable_spell_ids_collects_spells_from_owned_items(make_entry):
    entry_a = make_entry(slot=1, granted_spell_id=10)
    entry_b = make_entry(slot=2, granted_spell_id=20)

    assert usable_spell_ids([entry_a, entry_b]) == [10, 20]


def test_usable_spell_ids_deduplicates_repeated_spells(make_entry):
    entry_a = make_entry(slot=1, granted_spell_id=10)
    entry_b = make_entry(slot=2, granted_spell_id=10)
    entry_c = make_entry(slot=3, granted_spell_id=20)

    assert usable_spell_ids([entry_a, entry_b, entry_c]) == [10, 20]


def test_usable_spell_ids_treats_blessing_item_like_any_other(make_entry):
    # No special branch exists for blessing items; a blessing-granted spell
    # participates in the same set/order logic as a pool item's spell.
    blessing_entry = make_entry(slot=1, granted_spell_id=1)
    pool_entry = make_entry(slot=2, granted_spell_id=2)

    assert usable_spell_ids([blessing_entry, pool_entry]) == [1, 2]


def test_clamp_does_not_heal_when_max_increases():
    hp, mp = clamp_current_vitals(hp=100, mp=50, max_hp=600, max_mp=150)
    assert (hp, mp) == (100, 50)


def test_clamp_lowers_current_value_when_max_decreases():
    hp, mp = clamp_current_vitals(hp=100, mp=50, max_hp=80, max_mp=30)
    assert (hp, mp) == (80, 30)
