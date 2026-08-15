from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from yt_live_dungeon.persistence.models import RunEnemy


async def _setup(enemy_factory, enemy_group_factory, run_factory):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory()
    return enemy, group, run


def _base_kwargs(run_id, group_id, enemy_id, **overrides):
    defaults = dict(
        run_id=run_id,
        floor=1,
        group_id=group_id,
        enemy_id=enemy_id,
        order_in_group=1,
        role="master",
        max_hp=100,
        hp=100,
        max_mp=100,
        mp=100,
        mp_regen_rate=1,
        mp_regen_updated_at=datetime.now(UTC),
        attributes={},
        defeated_at=None,
    )
    defaults.update(overrides)
    return defaults


async def test_accepts_a_well_formed_row(
    db_session, enemy_factory, enemy_group_factory, run_factory
):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id)))
    await db_session.flush()  # no IntegrityError


async def test_rejects_invalid_role(db_session, enemy_factory, enemy_group_factory, run_factory):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    with pytest.raises(IntegrityError):
        db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, role="boss")))
        await db_session.flush()


async def test_rejects_order_in_group_below_one(
    db_session, enemy_factory, enemy_group_factory, run_factory
):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    with pytest.raises(IntegrityError):
        db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, order_in_group=0)))
        await db_session.flush()


async def test_allows_order_in_group_above_nine(
    db_session, enemy_factory, enemy_group_factory, run_factory
):
    """Unlike EnemyGroupMember's 1-9 template range, RunEnemy has no
    upper bound -- a future additional-spawn feature must be able to use
    order values beyond the initial group's 1-9."""
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, order_in_group=42)))
    await db_session.flush()  # no IntegrityError


async def test_rejects_negative_hp(db_session, enemy_factory, enemy_group_factory, run_factory):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    with pytest.raises(IntegrityError):
        db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, hp=-1)))
        await db_session.flush()


async def test_rejects_negative_mp(db_session, enemy_factory, enemy_group_factory, run_factory):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    with pytest.raises(IntegrityError):
        db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, mp=-1)))
        await db_session.flush()


async def test_rejects_negative_mp_regen_rate(
    db_session, enemy_factory, enemy_group_factory, run_factory
):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    with pytest.raises(IntegrityError):
        db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, mp_regen_rate=-1)))
        await db_session.flush()


async def test_rejects_zero_mp_regen_rate(
    db_session, enemy_factory, enemy_group_factory, run_factory
):
    """0 participants must never reach this table as a rate=0 row --
    spawn_group() refuses to spawn at all outside the 1-8 range (see
    features/floor/spawn.py), and this CHECK backs that up at the
    schema level too."""
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    with pytest.raises(IntegrityError):
        db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, mp_regen_rate=0)))
        await db_session.flush()


async def test_rejects_mp_regen_rate_above_eight(
    db_session, enemy_factory, enemy_group_factory, run_factory
):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    with pytest.raises(IntegrityError):
        db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, mp_regen_rate=9)))
        await db_session.flush()


@pytest.mark.parametrize("rate", [1, 8])
async def test_accepts_mp_regen_rate_at_range_boundaries(
    db_session, enemy_factory, enemy_group_factory, run_factory, rate
):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, mp_regen_rate=rate)))
    await db_session.flush()  # no IntegrityError


async def test_rejects_hp_above_max_hp(db_session, enemy_factory, enemy_group_factory, run_factory):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    with pytest.raises(IntegrityError):
        db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, hp=101, max_hp=100)))
        await db_session.flush()


async def test_rejects_mp_above_max_mp(db_session, enemy_factory, enemy_group_factory, run_factory):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    with pytest.raises(IntegrityError):
        db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, mp=101)))
        await db_session.flush()


async def test_rejects_max_mp_other_than_100(
    db_session, enemy_factory, enemy_group_factory, run_factory
):
    """Per obsidian/.../キャラクター/ステータス.md section 5: max MP is
    fixed at 100 for every combatant, never varied by floor or
    participant count."""
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)

    with pytest.raises(IntegrityError):
        db_session.add(
            RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, max_mp=20, mp=20))
        )
        await db_session.flush()


async def test_rejects_duplicate_run_floor_order(
    db_session, enemy_factory, enemy_group_factory, run_factory
):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)
    db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id)))
    await db_session.flush()

    with pytest.raises(IntegrityError):
        db_session.add(
            RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, role="minion"))
        )
        await db_session.flush()


async def test_rejects_a_second_master_for_the_same_run_and_floor(
    db_session, enemy_factory, enemy_group_factory, run_factory
):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)
    db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, order_in_group=1)))
    await db_session.flush()

    with pytest.raises(IntegrityError):
        db_session.add(
            RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, order_in_group=2, role="master"))
        )
        await db_session.flush()


async def test_allows_a_second_master_on_a_different_floor_of_the_same_run(
    db_session, enemy_factory, enemy_group_factory, run_factory
):
    enemy, group, run = await _setup(enemy_factory, enemy_group_factory, run_factory)
    db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, floor=1)))
    await db_session.flush()

    db_session.add(RunEnemy(**_base_kwargs(run.id, group.id, enemy.id, floor=2)))
    await db_session.flush()  # no IntegrityError -- different floor
