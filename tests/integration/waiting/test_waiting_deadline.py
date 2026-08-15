import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from yt_live_dungeon.features.waiting.deadline import ensure_waiting_deadline_evaluated
from yt_live_dungeon.persistence.models import EnemyGroup, RunEnemy, RunEvent, RunState

DEADLINE_AT = datetime(2026, 1, 1, tzinfo=UTC)


async def _isolate_group_draw(db_session, group_id) -> None:
    await db_session.execute(
        update(EnemyGroup).where(EnemyGroup.id != group_id).values(is_active=False)
    )


async def test_deadline_not_yet_reached_leaves_run_waiting(
    db_session, run_factory, adventurer_factory
):
    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=DEADLINE_AT)
    await adventurer_factory(run_id=run.id)

    just_before = DEADLINE_AT - timedelta(seconds=1)
    await ensure_waiting_deadline_evaluated(
        db_session, run.id, now=just_before, random_source=random.Random(1)
    )

    await db_session.refresh(run)
    assert run.state == RunState.WAITING


async def test_no_deadline_set_yet_is_left_untouched(db_session, run_factory):
    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=None)

    await ensure_waiting_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT, random_source=random.Random(1)
    )

    await db_session.refresh(run)
    assert run.state == RunState.WAITING


async def test_deadline_reached_with_participants_starts_floor_1(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    await _isolate_group_draw(db_session, group.id)

    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=DEADLINE_AT)
    ready_adventurer = await adventurer_factory(
        run_id=run.id, youtube_id="ready", waiting_ready_at=DEADLINE_AT
    )
    unready_adventurer = await adventurer_factory(
        run_id=run.id, youtube_id="unready", waiting_ready_at=None
    )

    await ensure_waiting_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT, random_source=random.Random(1)
    )

    await db_session.refresh(run)
    assert run.state == RunState.BATTLE
    assert run.current_floor == 1

    await db_session.refresh(ready_adventurer)
    await db_session.refresh(unready_adventurer)
    assert ready_adventurer.waiting_ready_at == DEADLINE_AT  # untouched -- was already ready
    assert unready_adventurer.waiting_ready_at == DEADLINE_AT  # forced ready by the timeout

    events = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "adventurer_ready"
            )
        )
    ).scalars().all()
    assert len(events) == 1  # only the not-yet-ready adventurer gets a forced event
    assert events[0].body == {"adventurer": str(unready_adventurer.id), "reason": "timeout"}

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 1)
        )
    ).scalars().all()
    assert len(spawned) == 1
    assert spawned[0].mp_regen_rate == 2


async def test_deadline_reached_with_zero_participants_leaves_run_waiting(
    db_session, run_factory
):
    """Per obsidian/.../進行/参加受付.md, this case (deadline reached with
    no participants remaining) is not defined by the game spec. Rather
    than guess a terminal state or spawn an enemy-less BATTLE, this stays
    a safe no-op: run.state remains WAITING. See features/waiting/deadline.py.
    """
    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=DEADLINE_AT)

    await ensure_waiting_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT, random_source=random.Random(1)
    )

    await db_session.refresh(run)
    assert run.state == RunState.WAITING

    spawned = (
        await db_session.execute(select(RunEnemy).where(RunEnemy.run_id == run.id))
    ).scalars().all()
    assert spawned == []


async def test_deadline_evaluation_is_idempotent_once_started(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    await _isolate_group_draw(db_session, group.id)

    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=DEADLINE_AT)
    await adventurer_factory(run_id=run.id)

    await ensure_waiting_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT, random_source=random.Random(1)
    )
    await ensure_waiting_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT + timedelta(hours=1), random_source=random.Random(1)
    )

    floor_started_events = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "floor_started"
            )
        )
    ).scalars().all()
    assert len(floor_started_events) == 1

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 1)
        )
    ).scalars().all()
    assert len(spawned) == 1


async def test_master_and_minion_mp_regen_rate_after_waiting_triggered_start(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    """The master's MP regen rate becomes the floor-start participant
    count (obsidian/.../ダンジョン/フロア補正.md section 5). Minions are
    documented there as exempt from this multiplier, but
    features/floor/spawn.py -- reused as-is by start_run(), unmodified
    by this task -- currently assigns the *same* multiplied rate to
    every group member regardless of role. This mirrors the existing,
    already-locked-in behavior asserted by
    tests/integration/floor/test_run_start.py::
    test_start_run_gives_master_and_minion_the_same_mp_regen_rate; see
    this task's completion report for this pre-existing spec/implementation
    discrepancy, which is out of scope to fix here.
    """
    master_enemy = await enemy_factory()
    minion_enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[
            {"order_in_group": 1, "enemy_id": master_enemy.id, "role": "master"},
            {"order_in_group": 2, "enemy_id": minion_enemy.id, "role": "minion"},
        ]
    )
    await _isolate_group_draw(db_session, group.id)

    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=DEADLINE_AT)
    for i in range(3):
        await adventurer_factory(
            run_id=run.id, youtube_id=f"viewer-{i}", waiting_ready_at=DEADLINE_AT
        )

    await ensure_waiting_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT, random_source=random.Random(1)
    )

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 1)
        )
    ).scalars().all()
    assert len(spawned) == 2
    master = next(row for row in spawned if row.role == "master")
    minion = next(row for row in spawned if row.role == "minion")
    assert master.mp_regen_rate == 3
    assert minion.mp_regen_rate == 3  # see docstring: spec says this should be 1 (base rate)


async def test_deadline_evaluation_is_a_no_op_when_run_is_not_waiting(db_session, run_factory):
    run = await run_factory(state=RunState.BATTLE)

    result = await ensure_waiting_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT, random_source=random.Random(1)
    )

    assert result.state == RunState.BATTLE
