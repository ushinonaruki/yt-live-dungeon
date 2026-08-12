import random
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, update

from yt_live_dungeon.domain.errors import EnemyGroupConfigurationError, InvalidParticipantCountError
from yt_live_dungeon.features.run.start import start_run
from yt_live_dungeon.persistence.models import EnemyGroup, RunEnemy, RunEvent, RunState

NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def _isolate_group_draw(db_session, group_id) -> None:
    """list_active_group_ids() draws from *every* active EnemyGroup
    visible in this transaction. The shared test DB is never reset
    between tests, so other tests' committed groups (real-commit
    concurrency scenarios, seed data) would otherwise also be in that
    population, making a seeded RandomSource's draw non-deterministic.
    Deactivating every other group only inside this test's own
    (rolled-back) transaction fixes that without touching real
    committed state. Passing group_id=None isolates down to zero active
    groups, for the "no active groups" failure case."""
    stmt = update(EnemyGroup).values(is_active=False)
    if group_id is not None:
        stmt = stmt.where(EnemyGroup.id != group_id)
    await db_session.execute(stmt)


async def test_start_run_spawns_floor_1_run_enemies(
    db_session, run_factory, enemy_factory, enemy_group_factory, adventurer_factory
):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    await _isolate_group_draw(db_session, group.id)
    run = await run_factory(state=RunState.WAITING, current_floor=1)
    await adventurer_factory(run_id=run.id)

    await start_run(db_session, run, now=NOW, random_source=random.Random(1))

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 1)
        )
    ).scalars().all()
    assert len(spawned) == 1
    assert spawned[0].role == "master"
    assert spawned[0].group_id == group.id


async def test_start_run_sets_floor_1_and_battle_state(
    db_session, run_factory, enemy_factory, enemy_group_factory, adventurer_factory
):
    enemy = await enemy_factory()
    await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.WAITING, current_floor=1)
    await adventurer_factory(run_id=run.id)

    await start_run(db_session, run, now=NOW, random_source=random.Random(1))

    assert run.current_floor == 1
    assert run.state == RunState.BATTLE


async def test_start_run_saves_a_next_group_for_floor_2(
    db_session, run_factory, enemy_factory, enemy_group_factory, adventurer_factory
):
    enemy = await enemy_factory()
    await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.WAITING, current_floor=1)
    await adventurer_factory(run_id=run.id)

    await start_run(db_session, run, now=NOW, random_source=random.Random(1))

    assert run.next_group_id is not None


async def test_start_run_records_floor_started_event(
    db_session, run_factory, enemy_factory, enemy_group_factory, adventurer_factory
):
    enemy = await enemy_factory()
    await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.WAITING, current_floor=1)
    await adventurer_factory(run_id=run.id)

    await start_run(db_session, run, now=NOW, random_source=random.Random(1))

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "floor_started"
            )
        )
    ).scalar_one()
    assert event.body == {"floor": 1}


async def test_start_run_raises_when_no_active_groups_exist(db_session, run_factory):
    await _isolate_group_draw(db_session, None)
    run = await run_factory(state=RunState.WAITING, current_floor=1)

    with pytest.raises(EnemyGroupConfigurationError):
        await start_run(db_session, run, now=NOW, random_source=random.Random(1))

    assert run.state == RunState.WAITING


async def test_start_run_rejects_zero_participants(
    db_session, run_factory, enemy_factory, enemy_group_factory
):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    await _isolate_group_draw(db_session, group.id)
    run = await run_factory(state=RunState.WAITING, current_floor=1)

    with pytest.raises(InvalidParticipantCountError):
        await start_run(db_session, run, now=NOW, random_source=random.Random(1))

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 1)
        )
    ).scalars().all()
    assert spawned == []
    assert run.state == RunState.WAITING


async def test_start_run_rejects_nine_participants(
    db_session, run_factory, enemy_factory, enemy_group_factory, adventurer_factory
):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    await _isolate_group_draw(db_session, group.id)
    run = await run_factory(state=RunState.WAITING, current_floor=1)
    for _ in range(9):
        await adventurer_factory(run_id=run.id)

    with pytest.raises(InvalidParticipantCountError):
        await start_run(db_session, run, now=NOW, random_source=random.Random(1))

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 1)
        )
    ).scalars().all()
    assert spawned == []
    assert run.state == RunState.WAITING


@pytest.mark.parametrize("participant_count", [1, 4, 8])
async def test_start_run_snapshots_mp_regen_rate_from_participant_count(
    db_session, run_factory, enemy_factory, enemy_group_factory, adventurer_factory,
    participant_count,
):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    await _isolate_group_draw(db_session, group.id)
    run = await run_factory(state=RunState.WAITING, current_floor=1)
    for _ in range(participant_count):
        await adventurer_factory(run_id=run.id)

    await start_run(db_session, run, now=NOW, random_source=random.Random(1))

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 1)
        )
    ).scalar_one()
    assert spawned.mp_regen_rate == participant_count
    assert spawned.mp_regen_updated_at == NOW


async def test_start_run_gives_master_and_minion_the_same_mp_regen_rate(
    db_session, run_factory, enemy_factory, enemy_group_factory, adventurer_factory,
):
    master_enemy = await enemy_factory()
    minion_enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[
            {"order_in_group": 1, "enemy_id": master_enemy.id, "role": "master"},
            {"order_in_group": 2, "enemy_id": minion_enemy.id, "role": "minion"},
        ]
    )
    await _isolate_group_draw(db_session, group.id)
    run = await run_factory(state=RunState.WAITING, current_floor=1)
    for _ in range(3):
        await adventurer_factory(run_id=run.id)

    await start_run(db_session, run, now=NOW, random_source=random.Random(1))

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 1)
        )
    ).scalars().all()
    assert len(spawned) == 2
    assert {row.mp_regen_rate for row in spawned} == {3}
