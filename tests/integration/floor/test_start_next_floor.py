import random
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from yt_live_dungeon.domain.errors import EnemyGroupConfigurationError, InvalidStatModifierError
from yt_live_dungeon.features.floor.start import start_next_floor
from yt_live_dungeon.persistence.models import RunEnemy, RunEvent, RunState

NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def _setup_group(enemy_factory, enemy_group_factory, *, base_max_hp: int = 100):
    enemy = await enemy_factory(base_max_hp=base_max_hp)
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    return group, enemy


async def test_start_next_floor_heals_mp_to_the_fixed_max_regardless_of_items(
    db_session,
    spell_factory,
    item_factory,
    run_factory,
    adventurer_factory,
    inventory_item_factory,
    enemy_factory,
    enemy_group_factory,
):
    """Per obsidian/.../キャラクター/ステータス.md section 5 and section
    9: max MP is fixed at 100 for every combatant and is never affected
    by items; floor start heals current MP to that fixed max regardless
    of what items a participant holds."""
    group, _enemy = await _setup_group(enemy_factory, enemy_group_factory)
    spell = await spell_factory()
    item = await item_factory(granted_spell_id=spell.id, base_stat_modifiers={"max_hp": 30})
    run = await run_factory(state=RunState.CAMP, current_floor=1, next_group_id=group.id)
    adventurer = await adventurer_factory(run_id=run.id, hp=100, mp=5)
    await inventory_item_factory(adventurer.id, item.id, slot=1, current_level=1)

    await start_next_floor(db_session, run, [adventurer], now=NOW, random_source=random.Random(1))

    assert adventurer.mp == 100


async def test_start_next_floor_does_not_change_hp(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    group, _enemy = await _setup_group(enemy_factory, enemy_group_factory)
    run = await run_factory(state=RunState.CAMP, current_floor=1, next_group_id=group.id)
    adventurer = await adventurer_factory(run_id=run.id, hp=123, mp=10)

    await start_next_floor(db_session, run, [adventurer], now=NOW, random_source=random.Random(1))

    assert adventurer.hp == 123


async def test_start_next_floor_increments_floor_and_sets_battle_state(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    group, _enemy = await _setup_group(enemy_factory, enemy_group_factory)
    run = await run_factory(state=RunState.CAMP, current_floor=3, next_group_id=group.id)
    adventurer = await adventurer_factory(run_id=run.id)

    await start_next_floor(db_session, run, [adventurer], now=NOW, random_source=random.Random(1))

    assert run.current_floor == 4
    assert run.state == RunState.BATTLE


async def test_start_next_floor_only_touches_the_given_participants(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    group, _enemy = await _setup_group(enemy_factory, enemy_group_factory)
    run = await run_factory(state=RunState.CAMP, current_floor=1, next_group_id=group.id)
    participant = await adventurer_factory(run_id=run.id, hp=100, mp=1)
    bystander = await adventurer_factory(run_id=run.id, hp=100, mp=1, is_participating=False)

    await start_next_floor(db_session, run, [participant], now=NOW, random_source=random.Random(1))

    assert participant.mp == 100  # healed to base_max_mp
    assert bystander.mp == 1  # untouched -- not in the participants list


async def test_start_next_floor_records_floor_started_event(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    group, _enemy = await _setup_group(enemy_factory, enemy_group_factory)
    run = await run_factory(state=RunState.CAMP, current_floor=5, next_group_id=group.id)
    adventurer = await adventurer_factory(run_id=run.id)

    await start_next_floor(db_session, run, [adventurer], now=NOW, random_source=random.Random(1))

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "floor_started"
            )
        )
    ).scalar_one()
    assert event.body == {"floor": 6}


async def test_start_next_floor_raises_without_partial_update_on_invalid_item(
    db_session,
    spell_factory,
    item_factory,
    run_factory,
    adventurer_factory,
    inventory_item_factory,
    enemy_factory,
    enemy_group_factory,
):
    group, _enemy = await _setup_group(enemy_factory, enemy_group_factory)
    spell = await spell_factory()
    broken_item = await item_factory(
        granted_spell_id=spell.id, base_stat_modifiers={"not_a_real_stat": 1}
    )
    run = await run_factory(state=RunState.CAMP, current_floor=2, next_group_id=group.id)
    adventurer = await adventurer_factory(run_id=run.id, hp=50, mp=5)
    await inventory_item_factory(adventurer.id, broken_item.id, slot=1, current_level=1)

    with pytest.raises(InvalidStatModifierError):
        await start_next_floor(
            db_session, run, [adventurer], now=NOW, random_source=random.Random(1)
        )

    # the floor/state fields this function would otherwise set are after
    # the per-participant recompute loop in source order, and nothing was
    # flushed/committed, so they remain exactly as before the call
    assert run.current_floor == 2
    assert run.state == RunState.CAMP
    assert adventurer.mp == 5


async def test_start_next_floor_raises_when_next_group_id_is_unset(
    db_session, run_factory, adventurer_factory
):
    run = await run_factory(state=RunState.CAMP, current_floor=1, next_group_id=None)
    adventurer = await adventurer_factory(run_id=run.id)

    with pytest.raises(EnemyGroupConfigurationError):
        await start_next_floor(
            db_session, run, [adventurer], now=NOW, random_source=random.Random(1)
        )


async def test_start_next_floor_consumes_saved_next_group_without_redrawing(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    group, enemy = await _setup_group(enemy_factory, enemy_group_factory)
    other_enemy = await enemy_factory()
    other_group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": other_enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.CAMP, current_floor=1, next_group_id=group.id)
    adventurer = await adventurer_factory(run_id=run.id)

    # even with a seed that would draw `other_group` if asked to draw for
    # the *current* floor, start_next_floor() must still consume the
    # already-saved next_group_id, not redraw
    await start_next_floor(db_session, run, [adventurer], now=NOW, random_source=random.Random(999))

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 2)
        )
    ).scalars().all()
    assert len(spawned) == 1
    assert spawned[0].group_id == group.id
    assert spawned[0].enemy_id == enemy.id
    assert other_group.id != group.id  # sanity: they really are different groups


async def test_start_next_floor_spawns_run_enemies_for_the_new_floor(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    group, enemy = await _setup_group(enemy_factory, enemy_group_factory, base_max_hp=200)
    run = await run_factory(state=RunState.CAMP, current_floor=1, next_group_id=group.id)
    adventurer = await adventurer_factory(run_id=run.id)

    await start_next_floor(db_session, run, [adventurer], now=NOW, random_source=random.Random(1))

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 2)
        )
    ).scalars().all()
    assert len(spawned) == 1
    assert spawned[0].role == "master"
    # floor 2 -> floor(200 * 1.10) = 220
    assert spawned[0].max_hp == 220
    assert spawned[0].hp == 220


async def test_start_next_floor_saves_a_new_next_group_unless_it_just_started_floor_100(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    group, _enemy = await _setup_group(enemy_factory, enemy_group_factory)
    run = await run_factory(state=RunState.CAMP, current_floor=1, next_group_id=group.id)
    adventurer = await adventurer_factory(run_id=run.id)

    await start_next_floor(db_session, run, [adventurer], now=NOW, random_source=random.Random(1))

    assert run.next_group_id is not None


async def test_start_next_floor_leaves_no_next_group_after_floor_100(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    group, _enemy = await _setup_group(enemy_factory, enemy_group_factory)
    run = await run_factory(state=RunState.CAMP, current_floor=99, next_group_id=group.id)
    adventurer = await adventurer_factory(run_id=run.id)

    await start_next_floor(db_session, run, [adventurer], now=NOW, random_source=random.Random(1))

    assert run.current_floor == 100
    assert run.next_group_id is None


async def test_start_next_floor_recomputes_mp_regen_rate_for_the_new_participant_count(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    """The new floor's enemies get a rate based on *this* floor-start's
    live participant count, independent of whatever rate the previous
    floor's (now-superseded) enemies were spawned with."""
    group, _enemy = await _setup_group(enemy_factory, enemy_group_factory)
    run = await run_factory(state=RunState.CAMP, current_floor=1, next_group_id=group.id)
    active = [await adventurer_factory(run_id=run.id) for _ in range(2)]
    # a third adventurer who is no longer an active participant must not
    # be counted
    await adventurer_factory(run_id=run.id, is_participating=False)

    await start_next_floor(db_session, run, active, now=NOW, random_source=random.Random(1))

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 2)
        )
    ).scalar_one()
    assert spawned.mp_regen_rate == 2
    assert spawned.mp_regen_updated_at == NOW


async def test_a_participants_death_after_floor_start_does_not_change_the_already_spawned_rate(
    db_session, run_factory, adventurer_factory, enemy_factory, enemy_group_factory
):
    group, _enemy = await _setup_group(enemy_factory, enemy_group_factory)
    run = await run_factory(state=RunState.CAMP, current_floor=1, next_group_id=group.id)
    survivor = await adventurer_factory(run_id=run.id)
    doomed = await adventurer_factory(run_id=run.id)

    await start_next_floor(
        db_session, run, [survivor, doomed], now=NOW, random_source=random.Random(1)
    )
    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 2)
        )
    ).scalar_one()
    assert spawned.mp_regen_rate == 2

    doomed.is_alive = False
    await db_session.flush()
    await db_session.refresh(spawned)

    assert spawned.mp_regen_rate == 2  # unchanged by the later death
