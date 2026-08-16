import random
from datetime import UTC, datetime

from sqlalchemy import select

from yt_live_dungeon.features.battle.master_defeat import check_and_handle_master_defeat
from yt_live_dungeon.persistence.models import RunCamp, RunEvent, RunState

NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def _setup_egregore(spell_factory, item_factory, egregore_factory, pool_entry_factory):
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    egregore = await egregore_factory(blessing_item_id=blessing_item.id)
    pool_a = await item_factory(granted_spell_id=spell.id)
    pool_b = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(egregore_id=egregore.id, item_id=pool_a.id)
    await pool_entry_factory(egregore_id=egregore.id, item_id=pool_b.id)
    return egregore


async def test_master_defeat_starts_camp_before_floor_100(
    db_session,
    spell_factory,
    item_factory,
    egregore_factory,
    pool_entry_factory,
    enemy_factory,
    enemy_group_factory,
    run_factory,
    run_enemy_factory,
):
    await _setup_egregore(spell_factory, item_factory, egregore_factory, pool_entry_factory)
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=5)
    master = await run_enemy_factory(
        run.id, 5, group.id, enemy.id, role="master", hp=0, defeated_at=NOW
    )

    await check_and_handle_master_defeat(db_session, run, now=NOW, random_source=random.Random(1))

    assert run.state == RunState.CAMP
    camp = (
        await db_session.execute(
            select(RunCamp).where(RunCamp.run_id == run.id, RunCamp.floor == 5)
        )
    ).scalar_one()
    assert camp.floor == 5
    assert master.defeated_at == NOW  # unchanged, just confirming setup


async def test_surviving_minions_do_not_block_breakthrough(
    db_session,
    spell_factory,
    item_factory,
    egregore_factory,
    pool_entry_factory,
    enemy_factory,
    enemy_group_factory,
    run_factory,
    run_enemy_factory,
):
    await _setup_egregore(spell_factory, item_factory, egregore_factory, pool_entry_factory)
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[
            {"order_in_group": 1, "enemy_id": enemy.id, "role": "master"},
            {"order_in_group": 2, "enemy_id": enemy.id, "role": "minion"},
        ]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await run_enemy_factory(
        run.id, 1, group.id, enemy.id, order_in_group=1, role="master", hp=0, defeated_at=NOW
    )
    await run_enemy_factory(
        run.id, 1, group.id, enemy.id, order_in_group=2, role="minion", hp=100, defeated_at=None
    )

    await check_and_handle_master_defeat(db_session, run, now=NOW, random_source=random.Random(1))

    assert run.state == RunState.CAMP


async def test_minion_defeat_alone_does_not_trigger_breakthrough(
    db_session,
    enemy_factory,
    enemy_group_factory,
    run_factory,
    run_enemy_factory,
):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[
            {"order_in_group": 1, "enemy_id": enemy.id, "role": "master"},
            {"order_in_group": 2, "enemy_id": enemy.id, "role": "minion"},
        ]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await run_enemy_factory(
        run.id, 1, group.id, enemy.id, order_in_group=1, role="master", hp=100, defeated_at=None
    )
    await run_enemy_factory(
        run.id, 1, group.id, enemy.id, order_in_group=2, role="minion", hp=0, defeated_at=NOW
    )

    await check_and_handle_master_defeat(db_session, run, now=NOW, random_source=random.Random(1))

    assert run.state == RunState.BATTLE


async def test_floor_100_master_defeat_ends_the_run_without_camp(
    db_session,
    enemy_factory,
    enemy_group_factory,
    run_factory,
    run_enemy_factory,
):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=100)
    await run_enemy_factory(run.id, 100, group.id, enemy.id, role="master", hp=0, defeated_at=NOW)

    await check_and_handle_master_defeat(db_session, run, now=NOW, random_source=random.Random(1))

    assert run.state == RunState.GAME_OVER
    assert run.ended_at == NOW

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "run_completed"
            )
        )
    ).scalar_one()
    assert event.body == {"floor": 100}

    camp_count = (
        await db_session.execute(select(RunCamp).where(RunCamp.run_id == run.id))
    ).scalars().all()
    assert camp_count == []


async def test_double_invocation_does_not_double_transition(
    db_session,
    spell_factory,
    item_factory,
    egregore_factory,
    pool_entry_factory,
    enemy_factory,
    enemy_group_factory,
    run_factory,
    run_enemy_factory,
):
    await _setup_egregore(spell_factory, item_factory, egregore_factory, pool_entry_factory)
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await run_enemy_factory(run.id, 1, group.id, enemy.id, role="master", hp=0, defeated_at=NOW)

    await check_and_handle_master_defeat(db_session, run, now=NOW, random_source=random.Random(1))
    assert run.state == RunState.CAMP

    # a second call must be a no-op: run.state is no longer BATTLE
    await check_and_handle_master_defeat(db_session, run, now=NOW, random_source=random.Random(2))

    camps = (
        await db_session.execute(
            select(RunCamp).where(RunCamp.run_id == run.id, RunCamp.floor == 1)
        )
    ).scalars().all()
    assert len(camps) == 1


async def test_previous_floors_defeated_master_does_not_trigger_current_floor_breakthrough(
    db_session,
    enemy_factory,
    enemy_group_factory,
    run_factory,
    run_enemy_factory,
):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=2)
    # floor 1's master was defeated long ago (history) -- irrelevant now
    await run_enemy_factory(run.id, 1, group.id, enemy.id, role="master", hp=0, defeated_at=NOW)
    # floor 2's master is alive
    await run_enemy_factory(run.id, 2, group.id, enemy.id, role="master", hp=100, defeated_at=None)

    await check_and_handle_master_defeat(db_session, run, now=NOW, random_source=random.Random(1))

    assert run.state == RunState.BATTLE
