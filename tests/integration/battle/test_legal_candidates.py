from datetime import UTC, datetime, timedelta

from yt_live_dungeon.features.battle.legal_candidates import (
    build_floor_combatants,
    build_legal_actions,
)
from yt_live_dungeon.persistence.models import RunState

NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def test_mp_insufficient_spell_is_excluded_from_candidates(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    expensive_spell = await spell_factory(mp_cost=999)
    enemy = await enemy_factory()
    await enemy_spell_factory(enemy.id, expensive_spell.id)
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await adventurer_factory(run_id=run.id)
    actor = await run_enemy_factory(run.id, 1, group.id, enemy.id, mp=5)

    combatants = await build_floor_combatants(db_session, run.id, 1, actor, now=NOW)
    legal_actions = await build_legal_actions(db_session, actor, combatants)

    assert legal_actions == ()


async def test_affordable_spell_targets_living_adventurers(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    spell = await spell_factory(mp_cost=0, target_rule="enemies")
    enemy = await enemy_factory()
    await enemy_spell_factory(enemy.id, spell.id)
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id)
    actor = await run_enemy_factory(run.id, 1, group.id, enemy.id, mp=20)

    combatants = await build_floor_combatants(db_session, run.id, 1, actor, now=NOW)
    legal_actions = await build_legal_actions(db_session, actor, combatants)

    assert len(legal_actions) == 1
    assert legal_actions[0].action_id == spell.id
    assert legal_actions[0].target_combinations == ((str(adventurer.id),),)


async def test_defeated_adventurer_is_not_a_legal_target(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    spell = await spell_factory(mp_cost=0, target_rule="enemies")
    enemy = await enemy_factory()
    await enemy_spell_factory(enemy.id, spell.id)
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await adventurer_factory(run_id=run.id, is_alive=False)
    actor = await run_enemy_factory(run.id, 1, group.id, enemy.id, mp=20)

    combatants = await build_floor_combatants(db_session, run.id, 1, actor, now=NOW)
    legal_actions = await build_legal_actions(db_session, actor, combatants)

    # no living adventurer to target -> the spell has zero legal target
    # combinations, so it is omitted entirely
    assert legal_actions == ()


async def test_allies_target_rule_resolves_to_other_living_enemies_on_same_floor(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    support_spell = await spell_factory(mp_cost=0, target_rule="allies")
    master_enemy = await enemy_factory(enemy_key="master-enemy")
    minion_enemy = await enemy_factory(enemy_key="minion-enemy")
    await enemy_spell_factory(master_enemy.id, support_spell.id)
    group = await enemy_group_factory(
        members=[
            {"order_in_group": 1, "enemy_id": master_enemy.id, "role": "master"},
            {"order_in_group": 2, "enemy_id": minion_enemy.id, "role": "minion"},
        ]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await adventurer_factory(run_id=run.id)
    actor = await run_enemy_factory(
        run.id, 1, group.id, master_enemy.id, order_in_group=1, role="master", mp=20
    )
    ally = await run_enemy_factory(
        run.id, 1, group.id, minion_enemy.id, order_in_group=2, role="minion", mp=20
    )

    combatants = await build_floor_combatants(db_session, run.id, 1, actor, now=NOW)
    legal_actions = await build_legal_actions(db_session, actor, combatants)

    assert legal_actions[0].target_combinations == ((str(ally.id),),)


async def test_target_rule_none_produces_a_single_empty_combination(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    self_spell = await spell_factory(mp_cost=0, target_rule="none")
    enemy = await enemy_factory()
    await enemy_spell_factory(enemy.id, self_spell.id)
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await adventurer_factory(run_id=run.id)
    actor = await run_enemy_factory(run.id, 1, group.id, enemy.id, mp=20)

    combatants = await build_floor_combatants(db_session, run.id, 1, actor, now=NOW)
    legal_actions = await build_legal_actions(db_session, actor, combatants)

    assert legal_actions[0].target_combinations == ((),)


async def test_a_previous_floors_enemy_never_appears_as_an_ally_or_target(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    spell = await spell_factory(mp_cost=0, target_rule="allies")
    enemy = await enemy_factory()
    await enemy_spell_factory(enemy.id, spell.id)
    group = await enemy_group_factory(
        members=[
            {"order_in_group": 1, "enemy_id": enemy.id, "role": "master"},
            {"order_in_group": 2, "enemy_id": enemy.id, "role": "minion"},
        ]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=2)
    await adventurer_factory(run_id=run.id)
    # a floor-1 enemy that must never be treated as a floor-2 ally
    await run_enemy_factory(
        run.id, 1, group.id, enemy.id, order_in_group=2, role="minion", mp=20
    )
    actor = await run_enemy_factory(
        run.id, 2, group.id, enemy.id, order_in_group=1, role="master", mp=20
    )

    combatants = await build_floor_combatants(db_session, run.id, 2, actor, now=NOW)
    legal_actions = await build_legal_actions(db_session, actor, combatants)

    # no living ally on *this* floor -- the previous floor's enemy must
    # not be picked up as a legal target
    assert legal_actions == ()


async def test_ally_snapshot_mp_is_projected_to_now_not_the_raw_db_column(
    db_session,
    enemy_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    master_enemy = await enemy_factory(enemy_key="master-enemy-2")
    minion_enemy = await enemy_factory(enemy_key="minion-enemy-2")
    group = await enemy_group_factory(
        members=[
            {"order_in_group": 1, "enemy_id": master_enemy.id, "role": "master"},
            {"order_in_group": 2, "enemy_id": minion_enemy.id, "role": "minion"},
        ]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await adventurer_factory(run_id=run.id)
    actor = await run_enemy_factory(
        run.id, 1, group.id, master_enemy.id, order_in_group=1, role="master", mp=20,
    )
    # the ally has been idle: its DB column is stale by design
    ally = await run_enemy_factory(
        run.id, 1, group.id, minion_enemy.id, order_in_group=2, role="minion",
        mp=0, max_mp=20, mp_regen_rate=4, mp_regen_updated_at=NOW - timedelta(seconds=5),
    )

    combatants = await build_floor_combatants(db_session, run.id, 1, actor, now=NOW)

    ally_snapshot = next(c for c in combatants.allies if c.combatant_id == str(ally.id))
    assert ally_snapshot.mp == 20  # 5s * rate=4 = 20, clamped at max_mp=20

    # snapshot-building must never write this projection back
    await db_session.refresh(ally)
    assert ally.mp == 0


async def test_actor_snapshot_mp_is_also_projected_to_now(
    db_session,
    enemy_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await adventurer_factory(run_id=run.id)
    actor = await run_enemy_factory(
        run.id, 1, group.id, enemy.id,
        mp=0, max_mp=100, mp_regen_rate=2, mp_regen_updated_at=NOW - timedelta(seconds=3),
    )

    combatants = await build_floor_combatants(db_session, run.id, 1, actor, now=NOW)

    assert combatants.actor.mp == 6  # 3s * rate=2

    # this is a pure projection too -- resolve_enemy_action() decides
    # separately whether to persist it, not build_floor_combatants()
    await db_session.refresh(actor)
    assert actor.mp == 0
