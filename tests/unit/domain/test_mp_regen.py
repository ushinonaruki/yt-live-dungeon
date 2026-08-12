from datetime import UTC, datetime, timedelta

from yt_live_dungeon.domain.mp_regen import apply_mp_regen

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_zero_elapsed_seconds_yields_no_change():
    outcome = apply_mp_regen(mp=5, max_mp=20, regen_rate=4, updated_at=T0, now=T0)

    assert outcome.mp == 5
    assert outcome.updated_at == T0


def test_one_elapsed_second_adds_exactly_the_rate():
    outcome = apply_mp_regen(
        mp=5, max_mp=20, regen_rate=4, updated_at=T0, now=T0 + timedelta(seconds=1)
    )

    assert outcome.mp == 9
    assert outcome.updated_at == T0 + timedelta(seconds=1)


def test_multiple_elapsed_seconds_multiplies_the_rate():
    outcome = apply_mp_regen(
        mp=0, max_mp=100, regen_rate=4, updated_at=T0, now=T0 + timedelta(seconds=6)
    )

    assert outcome.mp == 24
    assert outcome.updated_at == T0 + timedelta(seconds=6)


def test_fractional_seconds_are_truncated_and_kept_for_next_catch_up():
    outcome = apply_mp_regen(
        mp=0, max_mp=100, regen_rate=1, updated_at=T0, now=T0 + timedelta(seconds=2.9)
    )

    assert outcome.mp == 2  # only 2 whole seconds counted
    assert outcome.updated_at == T0 + timedelta(seconds=2)  # 0.9s remainder preserved


def test_clamps_at_max_mp():
    outcome = apply_mp_regen(
        mp=18, max_mp=20, regen_rate=4, updated_at=T0, now=T0 + timedelta(seconds=5)
    )

    assert outcome.mp == 20


def test_negative_elapsed_time_is_a_no_op():
    outcome = apply_mp_regen(
        mp=5, max_mp=20, regen_rate=4, updated_at=T0, now=T0 - timedelta(seconds=10)
    )

    assert outcome.mp == 5
    assert outcome.updated_at == T0


def test_total_regen_is_independent_of_how_often_it_is_computed():
    # one shot over 5.5s
    once = apply_mp_regen(
        mp=0, max_mp=100, regen_rate=3, updated_at=T0, now=T0 + timedelta(seconds=5.5)
    )

    # split into three catch-ups covering the same total span
    step1 = apply_mp_regen(
        mp=0, max_mp=100, regen_rate=3, updated_at=T0, now=T0 + timedelta(seconds=1.2)
    )
    step2 = apply_mp_regen(
        mp=step1.mp, max_mp=100, regen_rate=3,
        updated_at=step1.updated_at, now=T0 + timedelta(seconds=3.7),
    )
    step3 = apply_mp_regen(
        mp=step2.mp, max_mp=100, regen_rate=3,
        updated_at=step2.updated_at, now=T0 + timedelta(seconds=5.5),
    )

    assert step3.mp == once.mp


def test_zero_regen_rate_never_increases_mp():
    outcome = apply_mp_regen(
        mp=5, max_mp=20, regen_rate=0, updated_at=T0, now=T0 + timedelta(seconds=100)
    )

    assert outcome.mp == 5
