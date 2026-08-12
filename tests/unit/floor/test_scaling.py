from yt_live_dungeon.features.floor.scaling import calculate_enemy_floor_stats

BASE_ATTRIBUTES = {
    "rr": 5,
    "yr": 5,
    "yy": 5,
    "gy": 5,
    "gg": 5,
    "bg": 5,
    "bb": 5,
    "pb": 5,
    "pp": 5,
    "rp": 5,
}


def test_floor_1_applies_no_correction():
    stats = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=1)

    assert stats.max_hp == 100
    assert stats.attributes == BASE_ATTRIBUTES


def test_floor_2_scales_hp_to_110_percent_and_attributes_by_plus_1():
    stats = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=2)

    assert stats.max_hp == 110
    assert stats.attributes == {key: 6 for key in BASE_ATTRIBUTES}


def test_floor_10_scales_hp_to_190_percent_and_attributes_by_plus_9():
    stats = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=10)

    assert stats.max_hp == 190
    assert stats.attributes == {key: 14 for key in BASE_ATTRIBUTES}


def test_floor_100_scales_hp_to_1090_percent_and_attributes_by_plus_99():
    stats = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=100)

    assert stats.max_hp == 1090
    assert stats.attributes == {key: 104 for key in BASE_ATTRIBUTES}


def test_max_hp_rounds_down_when_scaling_produces_a_fraction():
    # floor(101 * (1 + 0.10 * 2)) = floor(101 * 1.2) = floor(121.2) = 121
    stats = calculate_enemy_floor_stats(101, BASE_ATTRIBUTES, floor=3)

    assert stats.max_hp == 121


def test_no_participant_count_factor_is_applied():
    """The formula takes no participant-count argument at all -- this
    test exists to make that omission explicit and intentional."""
    stats_a = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=5)
    stats_b = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=5)

    assert stats_a == stats_b


def test_does_not_use_the_old_25_percent_or_plus_5_formula():
    """Regression guard: an earlier (incorrect) spec version used 25%
    HP scaling per floor and +5 per floor on attributes. Floor 2 is
    enough to distinguish both from the confirmed 10%/+1 formulas."""
    stats = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=2)

    assert stats.max_hp != 125
    assert stats.attributes["rr"] != 10
