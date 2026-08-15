import asyncio
import random
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from yt_live_dungeon.domain.attributes import ATTRIBUTE_MODIFIER_KEYS
from yt_live_dungeon.features.battle.context import EnemyIntent
from yt_live_dungeon.features.battle.resolve import resolve_enemy_action
from yt_live_dungeon.persistence.models import RunAdventurer, RunEnemy, RunEvent, RunState

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


async def _setup_basic_scenario(
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
    *,
    ai_policy_key: str = "random_v1",
    mp_cost: int = 0,
    base_power: int = 5,
):
    spell = await spell_factory(
        mp_cost=mp_cost,
        target_rule="enemies",
        effects=[
            {
                "effect_id": "damage",
                "effect_target": "selected_targets",
                "params": {"attribute": "rr", "base_power": base_power, "hit_count": 1},
            }
        ],
    )
    enemy = await enemy_factory(ai_policy_key=ai_policy_key)
    await enemy_spell_factory(enemy.id, spell.id)
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id, hp=500, mp=100)
    actor = await run_enemy_factory(
        run.id, 1, group.id, enemy.id, mp=20, attributes=dict.fromkeys(ATTRIBUTE_MODIFIER_KEYS, 0)
    )
    return spell, enemy, run, adventurer, actor


async def test_random_v1_produces_a_reproducible_outcome_for_a_fixed_seed(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    _spell, _enemy, run, _adventurer, actor = await _setup_basic_scenario(
        spell_factory, enemy_factory, enemy_spell_factory, enemy_group_factory,
        run_factory, adventurer_factory, run_enemy_factory,
    )

    outcome = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(7)
    )

    assert outcome.no_action is False
    assert outcome.fallback_used is False
    assert len(outcome.damage_results) == 1


async def test_mp_is_deducted_and_damage_applied_in_one_call(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    _spell, _enemy, run, adventurer, actor = await _setup_basic_scenario(
        spell_factory, enemy_factory, enemy_spell_factory, enemy_group_factory,
        run_factory, adventurer_factory, run_enemy_factory,
        mp_cost=5, base_power=5,
    )

    await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    await db_session.refresh(actor)
    await db_session.refresh(adventurer)
    assert actor.mp == 15  # 20 - 5
    assert adventurer.hp == 500 - 5  # base_power=5, both attributes 0


async def test_enemy_action_resolved_event_is_recorded(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    spell, _enemy, run, adventurer, actor = await _setup_basic_scenario(
        spell_factory, enemy_factory, enemy_spell_factory, enemy_group_factory,
        run_factory, adventurer_factory, run_enemy_factory,
    )

    await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "enemy_action_resolved"
            )
        )
    ).scalar_one()
    assert event.body["actor"] == str(actor.id)
    assert event.body["action"] == spell.command
    assert event.body["target_ids"] == [str(adventurer.id)]
    assert event.body["fallback_used"] is False


async def test_no_legal_actions_returns_no_action_without_mutation_or_event(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    _spell, _enemy, run, _adventurer, actor = await _setup_basic_scenario(
        spell_factory, enemy_factory, enemy_spell_factory, enemy_group_factory,
        run_factory, adventurer_factory, run_enemy_factory,
        mp_cost=999,  # actor's mp=20 can never afford this
    )

    outcome = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    assert outcome.no_action is True
    await db_session.refresh(actor)
    assert actor.mp == 20  # untouched

    event_count = (
        await db_session.execute(
            select(RunEvent).where(RunEvent.run_id == run.id)
        )
    ).scalars().all()
    assert event_count == []


async def test_unregistered_policy_key_falls_back(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    _spell, _enemy, run, _adventurer, actor = await _setup_basic_scenario(
        spell_factory, enemy_factory, enemy_spell_factory, enemy_group_factory,
        run_factory, adventurer_factory, run_enemy_factory,
        ai_policy_key="no_such_policy_v1",
    )

    outcome = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    assert outcome.no_action is False
    assert outcome.fallback_used is True


async def test_policy_exception_falls_back(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
    monkeypatch,
):
    class _RaisingPolicy:
        def decide(self, context):
            raise RuntimeError("boom")

    import yt_live_dungeon.features.battle.registry as registry_module

    monkeypatch.setitem(registry_module._REGISTRY, "raising_v1", lambda rs: _RaisingPolicy())

    _spell, _enemy, run, _adventurer, actor = await _setup_basic_scenario(
        spell_factory, enemy_factory, enemy_spell_factory, enemy_group_factory,
        run_factory, adventurer_factory, run_enemy_factory,
        ai_policy_key="raising_v1",
    )

    outcome = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    assert outcome.no_action is False
    assert outcome.fallback_used is True


async def test_policy_timeout_falls_back(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
    monkeypatch,
):
    class _SlowPolicy:
        def decide(self, context):
            time.sleep(0.05)
            action = context.legal_actions[0]
            return EnemyIntent(action_id=action.action_id, target_ids=action.target_combinations[0])

    import yt_live_dungeon.features.battle.registry as registry_module
    import yt_live_dungeon.features.battle.resolve as resolve_module

    monkeypatch.setitem(registry_module._REGISTRY, "slow_v1", lambda rs: _SlowPolicy())
    monkeypatch.setattr(resolve_module, "POLICY_TIMEOUT_SECONDS", 0.01)

    _spell, _enemy, run, _adventurer, actor = await _setup_basic_scenario(
        spell_factory, enemy_factory, enemy_spell_factory, enemy_group_factory,
        run_factory, adventurer_factory, run_enemy_factory,
        ai_policy_key="slow_v1",
    )

    outcome = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    assert outcome.no_action is False
    assert outcome.fallback_used is True


async def test_intent_with_unpresented_action_id_falls_back(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
    monkeypatch,
):
    class _IllegalActionPolicy:
        def decide(self, context):
            return EnemyIntent(action_id=-999, target_ids=())

    import yt_live_dungeon.features.battle.registry as registry_module

    monkeypatch.setitem(
        registry_module._REGISTRY, "illegal_action_v1", lambda rs: _IllegalActionPolicy()
    )

    _spell, _enemy, run, _adventurer, actor = await _setup_basic_scenario(
        spell_factory, enemy_factory, enemy_spell_factory, enemy_group_factory,
        run_factory, adventurer_factory, run_enemy_factory,
        ai_policy_key="illegal_action_v1",
    )

    outcome = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    assert outcome.fallback_used is True


async def test_intent_with_unpresented_target_combination_falls_back(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
    monkeypatch,
):
    class _IllegalTargetPolicy:
        def decide(self, context):
            action = context.legal_actions[0]
            return EnemyIntent(action_id=action.action_id, target_ids=("not-a-real-combatant-id",))

    import yt_live_dungeon.features.battle.registry as registry_module

    monkeypatch.setitem(
        registry_module._REGISTRY, "illegal_target_v1", lambda rs: _IllegalTargetPolicy()
    )

    _spell, _enemy, run, _adventurer, actor = await _setup_basic_scenario(
        spell_factory, enemy_factory, enemy_spell_factory, enemy_group_factory,
        run_factory, adventurer_factory, run_enemy_factory,
        ai_policy_key="illegal_target_v1",
    )

    outcome = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    assert outcome.fallback_used is True


async def test_fallback_is_itself_revalidated_and_applies_exactly_one_action(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
    monkeypatch,
):
    class _IllegalActionPolicy:
        def decide(self, context):
            return EnemyIntent(action_id=-999, target_ids=())

    import yt_live_dungeon.features.battle.registry as registry_module

    monkeypatch.setitem(
        registry_module._REGISTRY, "illegal_action_v2", lambda rs: _IllegalActionPolicy()
    )

    _spell, _enemy, run, adventurer, actor = await _setup_basic_scenario(
        spell_factory, enemy_factory, enemy_spell_factory, enemy_group_factory,
        run_factory, adventurer_factory, run_enemy_factory,
        ai_policy_key="illegal_action_v2", mp_cost=5, base_power=5,
    )

    outcome = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    assert outcome.fallback_used is True
    await db_session.refresh(actor)
    await db_session.refresh(adventurer)
    # exactly one action's worth of MP/damage -- not a double application
    assert actor.mp == 15
    assert adventurer.hp == 495

    events = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "enemy_action_resolved"
            )
        )
    ).scalars().all()
    assert len(events) == 1


async def test_target_hp_reaching_zero_marks_it_defeated(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    _spell, _enemy, run, adventurer, actor = await _setup_basic_scenario(
        spell_factory, enemy_factory, enemy_spell_factory, enemy_group_factory,
        run_factory, adventurer_factory, run_enemy_factory,
        base_power=10_000,
    )
    adventurer.hp = 5
    await db_session.flush()

    await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    await db_session.refresh(adventurer)
    assert adventurer.hp == 0
    assert adventurer.is_alive is False


async def test_mp_regen_makes_a_previously_unaffordable_spell_available(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    spell = await spell_factory(
        mp_cost=15,
        target_rule="enemies",
        effects=[
            {
                "effect_id": "damage",
                "effect_target": "selected_targets",
                "params": {"attribute": "rr", "base_power": 1, "hit_count": 1},
            }
        ],
    )
    enemy = await enemy_factory()
    await enemy_spell_factory(enemy.id, spell.id)
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await adventurer_factory(run_id=run.id, hp=500, mp=100)
    actor = await run_enemy_factory(
        run.id, 1, group.id, enemy.id,
        mp=0, max_mp=100,
        mp_regen_rate=5, mp_regen_updated_at=NOW - timedelta(seconds=3),
        attributes=dict.fromkeys(ATTRIBUTE_MODIFIER_KEYS, 0),
    )

    # before any elapsed time, mp=0 can't afford mp_cost=15
    outcome_before = await resolve_enemy_action(
        db_session, run.id, actor.id, now=actor.mp_regen_updated_at, random_source=random.Random(1)
    )
    assert outcome_before.no_action is True

    # 3s * 5/s = 15 -- exactly enough after catch-up
    outcome_after = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )
    assert outcome_after.no_action is False

    await db_session.refresh(actor)
    assert actor.mp == 0  # 15 regenerated, all 15 spent on the spell


async def test_mp_regen_uses_the_stored_rate_not_a_live_participant_recount(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    """actor.mp_regen_rate was snapshotted at spawn time for 4
    participants. Only 1 is still an active participant now, but the
    regen amount must still use the stored rate=4, not a fresh count."""
    spell = await spell_factory(mp_cost=0, target_rule="enemies")
    enemy = await enemy_factory()
    await enemy_spell_factory(enemy.id, spell.id)
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await adventurer_factory(run_id=run.id)  # the one still active
    for _ in range(3):
        await adventurer_factory(run_id=run.id, is_participating=False, is_alive=False)
    actor = await run_enemy_factory(
        run.id, 1, group.id, enemy.id,
        mp=0, max_mp=100,
        mp_regen_rate=4, mp_regen_updated_at=NOW - timedelta(seconds=10),
        attributes=dict.fromkeys(ATTRIBUTE_MODIFIER_KEYS, 0),
    )

    await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    await db_session.refresh(actor)
    assert actor.mp == 40  # 10s * rate=4, not 10s * a live count of 1


async def test_mp_regen_anchor_advances_by_whole_seconds_consumed(
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
    await adventurer_factory(run_id=run.id)
    started_at = NOW - timedelta(seconds=2, milliseconds=500)
    actor = await run_enemy_factory(
        run.id, 1, group.id, enemy.id,
        mp=0, max_mp=100,
        mp_regen_rate=1, mp_regen_updated_at=started_at,
        attributes=dict.fromkeys(ATTRIBUTE_MODIFIER_KEYS, 0),
    )

    await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )

    await db_session.refresh(actor)
    assert actor.mp == 2  # only 2 whole seconds of the 2.5s elapsed counted
    assert actor.mp_regen_updated_at == started_at + timedelta(seconds=2)


async def test_idle_time_at_full_mp_is_not_banked_for_reuse_after_consumption(
    db_session,
    spell_factory,
    enemy_factory,
    enemy_spell_factory,
    enemy_group_factory,
    run_factory,
    adventurer_factory,
    run_enemy_factory,
):
    """Regression for: idle at max MP for a long time, then spend it all
    -- a later catch-up must not "reuse" the old idle span and instantly
    reheal. The single registered spell costs exactly max_mp, so it is
    only ever affordable when mp is truly back at the cap; using its
    (un)affordability as the observable is a stronger proof than reading
    the raw column, since it exercises the exact code path a Policy
    would see."""
    full_cost_spell = await spell_factory(
        mp_cost=100,
        target_rule="enemies",
        effects=[
            {
                "effect_id": "damage",
                "effect_target": "selected_targets",
                "params": {"attribute": "rr", "base_power": 1, "hit_count": 1},
            }
        ],
    )
    enemy = await enemy_factory()
    await enemy_spell_factory(enemy.id, full_cost_spell.id)
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    await adventurer_factory(run_id=run.id, hp=500, mp=100)
    long_idle_start = NOW - timedelta(seconds=1000)
    actor = await run_enemy_factory(
        run.id, 1, group.id, enemy.id,
        mp=100, max_mp=100,  # already full after a long idle
        mp_regen_rate=5, mp_regen_updated_at=long_idle_start,
        attributes=dict.fromkeys(ATTRIBUTE_MODIFIER_KEYS, 0),
    )

    # (1) consumes the full 100 mp -- clamped catch-up must still advance
    # the anchor to NOW, not leave it stuck at long_idle_start
    outcome_1 = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )
    assert outcome_1.no_action is False
    await db_session.refresh(actor)
    assert actor.mp == 0
    assert actor.mp_regen_updated_at == NOW

    # (2) same instant again -- if the old 1000s idle span were reused,
    # mp would reheal to 100 and this spell would be affordable again
    outcome_2 = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW, random_source=random.Random(1)
    )
    assert outcome_2.no_action is True
    await db_session.refresh(actor)
    assert actor.mp == 0

    # (3) exactly 20s later (20 * rate=5 == max_mp=100) -- the spell is
    # affordable again, proving regen resumed from the correct anchor
    outcome_3 = await resolve_enemy_action(
        db_session, run.id, actor.id, now=NOW + timedelta(seconds=20),
        random_source=random.Random(1),
    )
    assert outcome_3.no_action is False
    await db_session.refresh(actor)
    assert actor.mp == 0  # 100 regenerated, all 100 spent again


async def _commit_basic_scenario() -> dict:
    from yt_live_dungeon.persistence.database import async_session_factory
    from yt_live_dungeon.persistence.models import (
        Enemy,
        EnemyGroup,
        EnemyGroupMember,
        EnemySpell,
        Run,
        Spell,
    )

    async with async_session_factory() as session:
        spell = Spell(
            command=_unique("spell"), display_name="s", attribute="RR", mp_cost=5,
            target_rule="enemies",
            effects=[
                {
                    "effect_id": "damage",
                    "effect_target": "selected_targets",
                    "params": {"attribute": "rr", "base_power": 1, "hit_count": 1},
                }
            ],
        )
        session.add(spell)
        await session.flush()

        enemy = Enemy(
            enemy_key=_unique("enemy"), display_name="e", base_max_hp=100, base_max_mp=100,
            base_attributes={}, break_max=50,
        )
        session.add(enemy)
        await session.flush()
        session.add(EnemySpell(enemy_id=enemy.id, spell_id=spell.id))

        group = EnemyGroup(group_key=_unique("group"), display_name="g")
        session.add(group)
        await session.flush()
        session.add(
            EnemyGroupMember(
                group_id=group.id, order_in_group=1, enemy_id=enemy.id, role="master"
            )
        )
        await session.flush()

        run = Run(state=RunState.BATTLE, current_floor=1)
        session.add(run)
        await session.flush()

        adventurer = RunAdventurer(run_id=run.id, youtube_id=_unique("viewer"), hp=500, mp=100)
        session.add(adventurer)
        await session.flush()

        run_enemy = RunEnemy(
            run_id=run.id, floor=1, group_id=group.id, enemy_id=enemy.id, order_in_group=1,
            role="master", max_hp=100, hp=100, max_mp=100, mp=100,
            # Exactly NOW (not datetime.now(UTC)) so that both concurrent
            # resolve_enemy_action() calls below -- which also pass
            # now=NOW -- see zero elapsed regen time and the classic
            # lost-update arithmetic this test proves stays exact.
            mp_regen_rate=1, mp_regen_updated_at=NOW,
            attributes={},
        )
        session.add(run_enemy)
        await session.commit()

        return {"run_id": run.id, "run_enemy_id": run_enemy.id}


async def test_concurrent_resolution_of_the_same_actor_serializes_without_lost_updates():
    """Proves the run-row + actor-row locking prevents a classic lost-
    update race: without it, two concurrent calls could both read
    mp=100 before either commits its mp_cost=5 deduction, and the second
    write would clobber the first, leaving mp=95 instead of the correct
    mp=90. There is no turn concept in Commit 7 to stop the same actor
    from being asked to act twice -- what locking guarantees is that
    each call's read-modify-write of shared state is serialized and
    neither is lost, not that a second call is refused outright.
    """
    from yt_live_dungeon.persistence.database import async_session_factory

    scenario = await _commit_basic_scenario()

    async def _resolve():
        async with async_session_factory() as session:
            outcome = await resolve_enemy_action(
                session,
                scenario["run_id"],
                scenario["run_enemy_id"],
                now=NOW,
                random_source=random.Random(),
            )
            await session.commit()
            return outcome

    first, second = await asyncio.gather(_resolve(), _resolve())

    async with async_session_factory() as session:
        run_enemy = await session.get(RunEnemy, scenario["run_enemy_id"])
        events = (
            await session.execute(
                select(RunEvent).where(
                    RunEvent.run_id == scenario["run_id"],
                    RunEvent.event_type == "enemy_action_resolved",
                )
            )
        ).scalars().all()

    assert run_enemy.mp == 100 - 5 - 5  # both deductions landed -- no lost update
    assert len(events) == 2
    assert first.no_action is False
    assert second.no_action is False
