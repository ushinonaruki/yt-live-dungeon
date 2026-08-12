import random

from yt_live_dungeon.features.floor.group_draw import draw_group_id


def test_draw_is_reproducible_with_a_fixed_seed():
    group_ids = [1, 2, 3, 4, 5]

    first = draw_group_id(group_ids, random.Random(42))
    second = draw_group_id(group_ids, random.Random(42))

    assert first == second


def test_draw_returns_a_member_of_the_population():
    group_ids = [10, 20, 30]

    result = draw_group_id(group_ids, random.Random(1))

    assert result in group_ids


def test_draw_is_with_replacement_across_repeated_calls():
    """The same RandomSource instance drawing repeatedly must be able to
    return the same group id again -- past draws are never excluded."""
    group_ids = [1]  # a single-candidate population makes repetition certain

    results = [draw_group_id(group_ids, random.Random(1)) for _ in range(5)]

    assert results == [1, 1, 1, 1, 1]
