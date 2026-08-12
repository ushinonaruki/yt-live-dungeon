import json
import random

from yt_live_dungeon.features.battle.context import (
    CombatantSnapshot,
    EnemyDecisionContext,
    LegalActionCandidate,
)
from yt_live_dungeon.features.battle.fallback import DeterministicFallbackPolicy
from yt_live_dungeon.features.battle.policies.random_v1 import RandomEnemyPolicy


def _actor() -> CombatantSnapshot:
    return CombatantSnapshot(
        combatant_id="actor-1",
        kind="enemy",
        display_name="Slime",
        role="master",
        hp=100,
        max_hp=100,
        mp=20,
        max_mp=20,
        attributes={"rr": 5},
        is_alive=True,
    )


def _context(legal_actions) -> EnemyDecisionContext:
    return EnemyDecisionContext(
        run_id="11111111-1111-1111-1111-111111111111",
        floor=1,
        action_sequence=0,
        actor=_actor(),
        allies=(),
        enemies=(),
        legal_actions=tuple(legal_actions),
        policy_config={},
    )


def test_random_v1_returns_a_reproducible_intent_for_a_fixed_seed():
    legal_actions = [
        LegalActionCandidate(
            action_id=1, command="bite", mp_cost=0, target_rule="enemies",
            target_combinations=(("t1",), ("t2",)),
        ),
        LegalActionCandidate(
            action_id=2, command="claw", mp_cost=5, target_rule="enemies",
            target_combinations=(("t1",),),
        ),
    ]
    context = _context(legal_actions)

    first = RandomEnemyPolicy(random.Random(7)).decide(context)
    second = RandomEnemyPolicy(random.Random(7)).decide(context)

    assert first == second


def test_random_v1_only_returns_a_presented_action_and_target_combination():
    legal_actions = [
        LegalActionCandidate(
            action_id=1, command="bite", mp_cost=0, target_rule="enemies",
            target_combinations=(("t1",), ("t2",)),
        ),
    ]
    context = _context(legal_actions)

    for seed in range(20):
        intent = RandomEnemyPolicy(random.Random(seed)).decide(context)
        assert intent.action_id == 1
        assert intent.target_ids in (("t1",), ("t2",))


def test_deterministic_fallback_picks_the_lowest_action_id_and_stable_first_target():
    legal_actions = [
        LegalActionCandidate(
            action_id=5, command="claw", mp_cost=0, target_rule="enemies",
            target_combinations=(("t2",), ("t1",)),
        ),
        LegalActionCandidate(
            action_id=2, command="bite", mp_cost=0, target_rule="enemies",
            target_combinations=(("t9",), ("t1",)),
        ),
    ]
    context = _context(legal_actions)

    intent = DeterministicFallbackPolicy().decide(context)

    assert intent.action_id == 2
    assert intent.target_ids == ("t1",)


def test_deterministic_fallback_is_stable_across_repeated_calls():
    legal_actions = [
        LegalActionCandidate(
            action_id=3, command="bite", mp_cost=0, target_rule="enemies",
            target_combinations=(("t1",), ("t2",)),
        ),
    ]
    context = _context(legal_actions)

    first = DeterministicFallbackPolicy().decide(context)
    second = DeterministicFallbackPolicy().decide(context)

    assert first == second


def test_context_contains_no_orm_session_or_redis_objects():
    """A structural proxy for "PolicyへORM model・DB session・Redis client
    を渡さない": every field of a real Context must be JSON-serializable
    plain data -- an ORM model, AsyncSession, or Redis client would not
    be."""
    legal_actions = [
        LegalActionCandidate(
            action_id=1, command="bite", mp_cost=0, target_rule="enemies",
            target_combinations=(("t1",),),
        ),
    ]
    context = _context(legal_actions)

    payload = {
        "run_id": context.run_id,
        "floor": context.floor,
        "action_sequence": context.action_sequence,
        "actor": context.actor.__dict__,
        "allies": [a.__dict__ for a in context.allies],
        "enemies": [e.__dict__ for e in context.enemies],
        "legal_actions": [
            {
                "action_id": a.action_id,
                "command": a.command,
                "mp_cost": a.mp_cost,
                "target_rule": a.target_rule,
                "target_combinations": [list(c) for c in a.target_combinations],
            }
            for a in context.legal_actions
        ],
        "policy_config": context.policy_config,
    }

    json.dumps(payload)  # raises TypeError if anything isn't plain data
