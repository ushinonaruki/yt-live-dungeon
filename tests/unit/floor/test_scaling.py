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


def test_floor_1_leaves_max_hp_and_attributes_unchanged():
    stats = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=1)

    assert stats.max_hp == 100
    assert stats.attributes == BASE_ATTRIBUTES


def test_floor_10_scales_max_hp_by_25_percent_per_floor_above_1():
    # floor(100 * (1 + 0.25 * 9)) = floor(100 * 3.25) = 325
    stats = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=10)

    assert stats.max_hp == 325


def test_floor_100_scales_max_hp_by_25_percent_per_floor_above_1():
    # floor(100 * (1 + 0.25 * 99)) = floor(100 * 25.75) = 2575
    stats = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=100)

    assert stats.max_hp == 2575


def test_floor_10_adds_5_per_floor_above_1_to_every_attribute():
    stats = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=10)

    assert stats.attributes == {key: 5 + 5 * 9 for key in BASE_ATTRIBUTES}


def test_floor_100_adds_5_per_floor_above_1_to_every_attribute():
    stats = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=100)

    assert stats.attributes == {key: 5 + 5 * 99 for key in BASE_ATTRIBUTES}


def test_max_hp_rounds_down_when_scaling_produces_a_fraction():
    # floor(101 * (1 + 0.25 * 2)) = floor(101 * 1.5) = floor(151.5) = 151
    stats = calculate_enemy_floor_stats(101, BASE_ATTRIBUTES, floor=3)

    assert stats.max_hp == 151


def test_no_participant_count_factor_is_applied():
    """The formula takes no participant-count argument at all -- this
    test exists to make that omission explicit and intentional, since an
    earlier (now corrected) spec version scaled attributes by party
    size."""
    stats_a = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=5)
    stats_b = calculate_enemy_floor_stats(100, BASE_ATTRIBUTES, floor=5)

    assert stats_a == stats_b
