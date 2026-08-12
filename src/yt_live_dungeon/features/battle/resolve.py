import time
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.mp_regen import apply_mp_regen
from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.battle.context import (
    EnemyDecisionContext,
    EnemyIntent,
    LegalActionCandidate,
)
from yt_live_dungeon.features.battle.effects import DamageResult, resolve_effects
from yt_live_dungeon.features.battle.fallback import DeterministicFallbackPolicy
from yt_live_dungeon.features.battle.legal_candidates import (
    build_floor_combatants,
    build_legal_actions,
)
from yt_live_dungeon.features.battle.master_defeat import check_and_handle_master_defeat
from yt_live_dungeon.features.battle.registry import resolve_policy
from yt_live_dungeon.persistence.models import RunAdventurer, RunEnemy
from yt_live_dungeon.persistence.queries.enemy import get_enemy
from yt_live_dungeon.persistence.queries.event import append_event
from yt_live_dungeon.persistence.queries.run import get_run_for_update
from yt_live_dungeon.persistence.queries.run_enemy import get_run_enemy
from yt_live_dungeon.persistence.queries.spell import get_spell

POLICY_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class ResolveActionOutcome:
    no_action: bool
    fallback_used: bool
    action_id: int | None
    target_ids: tuple[str, ...]
    damage_results: tuple[DamageResult, ...]


async def resolve_enemy_action(
    session: AsyncSession,
    run_id: uuid.UUID,
    run_enemy_id: uuid.UUID,
    *,
    now: datetime,
    random_source: RandomSource,
    action_sequence: int = 0,
) -> ResolveActionOutcome:
    """Resolves exactly one enemy's turn: builds a decision Context from
    current DB state -- every enemy snapshot in it (the actor's own
    included) shows mp projected to `now`, without persisting anything
    yet -- asks its EnemyPolicy (via the registry, falling back
    deterministically on any failure), re-validates the returned Intent
    against the same legal candidates the Policy was given, and -- only
    for a validated Intent -- persists the actor's MP regen catch-up
    together with MP cost, Damage, and defeat state in this same
    transaction, then checks whether the floor's master was just
    defeated.

    The projected mp used to decide legal_actions and build the Policy's
    Context (combatants.actor.mp) is the exact same value later written
    to `actor.mp` before the cost deduction -- there is no separate
    "live" MP anywhere else in this call.

    Never commits/rollbacks -- the caller owns the transaction (there is
    no dispatcher/HTTP entry point for this in Commit 7; callers are
    tests today). Locks the run row and the acting RunEnemy row FOR
    UPDATE for the whole call, which is what actually prevents double
    application under concurrency -- not any identifier carried in the
    Context or Intent.

    Returns a no_action outcome (no mutation, no event) if the actor is
    no longer a valid, living combatant on the run's current floor, or
    if it has zero legal actions right now -- obsidian/.../マスターと
    ミニオン.md section 13 leaves the game-level handling of "no legal
    action" undefined, so this stays a purely technical result. Because
    MP regen catch-up is only ever *persisted* once we're past this
    check, a no_action outcome truly leaves the actor row untouched --
    an idle enemy that never finds an affordable action doesn't
    accumulate any different state than one that was never queried.
    """
    run = await get_run_for_update(session, run_id)
    actor = await get_run_enemy(session, run_enemy_id, for_update=True)

    if (
        actor is None
        or actor.run_id != run_id
        or actor.floor != run.current_floor
        or actor.defeated_at is not None
    ):
        return ResolveActionOutcome(
            no_action=True, fallback_used=False, action_id=None, target_ids=(), damage_results=()
        )

    combatants = await build_floor_combatants(session, run_id, run.current_floor, actor, now=now)
    legal_actions = await build_legal_actions(session, actor, combatants)

    if not legal_actions:
        return ResolveActionOutcome(
            no_action=True, fallback_used=False, action_id=None, target_ids=(), damage_results=()
        )

    # Only now that an action will actually be taken do we persist the
    # actor's regen catch-up -- this matches the exact projection
    # combatants.actor.mp already reflects (same actor.mp/rate/anchor,
    # same `now`), so nothing downstream re-derives a different number.
    regen = apply_mp_regen(
        mp=actor.mp,
        max_mp=actor.max_mp,
        regen_rate=actor.mp_regen_rate,
        updated_at=actor.mp_regen_updated_at,
        now=now,
    )
    actor.mp = regen.mp
    actor.mp_regen_updated_at = regen.updated_at

    enemy_master = await get_enemy(session, actor.enemy_id)
    context = EnemyDecisionContext(
        run_id=str(run_id),
        floor=run.current_floor,
        action_sequence=action_sequence,
        actor=combatants.actor,
        allies=combatants.allies,
        enemies=combatants.enemies,
        legal_actions=legal_actions,
        policy_config=dict(enemy_master.ai_policy_config),
    )

    intent, fallback_used = _decide_with_fallback(
        enemy_master.ai_policy_key, context, random_source
    )

    chosen_action = next(a for a in legal_actions if a.action_id == intent.action_id)
    target_snapshots = [
        combatant
        for combatant in (combatants.actor, *combatants.allies, *combatants.enemies)
        if combatant.combatant_id in intent.target_ids
    ]

    # Defense in depth: re-check the actor can still afford this action.
    # The run+actor locks held since the start of this call already rule
    # out any real concurrent change, so this should never actually
    # differ from what build_legal_actions() already confirmed -- but a
    # future Context/Intent boundary that doesn't hold the lock for the
    # whole call (e.g. an out-of-process Policy) would need exactly this
    # check to still be safe.
    if actor.mp < chosen_action.mp_cost:
        intent = DeterministicFallbackPolicy().decide(context)
        fallback_used = True
        chosen_action = next(a for a in legal_actions if a.action_id == intent.action_id)
        target_snapshots = [
            combatant
            for combatant in (combatants.actor, *combatants.allies, *combatants.enemies)
            if combatant.combatant_id in intent.target_ids
        ]

    spell = await get_spell(session, intent.action_id)
    damage_results = resolve_effects(combatants.actor, target_snapshots, spell.effects)

    actor.mp -= chosen_action.mp_cost

    for result in damage_results:
        await _apply_damage(session, run_id, result, now=now)

    await append_event(
        session,
        run_id,
        "enemy_action_resolved",
        {
            "actor": str(actor.id),
            "action": spell.command,
            "target_ids": list(intent.target_ids),
            "fallback_used": fallback_used,
            "damage": [{"target": r.target_id, "amount": r.amount} for r in damage_results],
        },
    )

    await check_and_handle_master_defeat(session, run, now=now, random_source=random_source)

    return ResolveActionOutcome(
        no_action=False,
        fallback_used=fallback_used,
        action_id=intent.action_id,
        target_ids=intent.target_ids,
        damage_results=tuple(damage_results),
    )


def _decide_with_fallback(
    policy_key: str, context: EnemyDecisionContext, random_source: RandomSource
) -> tuple[EnemyIntent, bool]:
    policy = resolve_policy(policy_key, random_source)

    intent: EnemyIntent | None = None
    if policy is not None:
        try:
            intent = _decide_with_soft_timeout(policy, context)
        except Exception:
            intent = None

    if intent is None or not _is_legal_intent(intent, context.legal_actions):
        fallback_intent = DeterministicFallbackPolicy().decide(context)
        # The fallback intent goes through the same re-validation as any
        # other -- it should always pass by construction (it is derived
        # from these same legal_actions), so failing here means the
        # fallback policy itself is broken, not that the primary policy
        # misbehaved.
        if not _is_legal_intent(fallback_intent, context.legal_actions):
            raise AssertionError("fallback policy produced an illegal intent")
        return fallback_intent, True

    return intent, False


def _decide_with_soft_timeout(policy, context: EnemyDecisionContext) -> EnemyIntent | None:
    """Measures how long policy.decide() took and discards the result if
    it exceeded POLICY_TIMEOUT_SECONDS. This cannot pre-empt a genuinely
    hanging synchronous call (Commit 7 adds no threads, async workers,
    or job queue to do that) -- it only prevents an unreasonably slow
    Policy's result from being trusted after the fact. random_v1 is
    synchronous and fast, so this never fires for it in practice; it
    exists for a future Policy implementation and is exercised directly
    in tests via a deliberately slow stub Policy.
    """
    started_at = time.monotonic()
    result = policy.decide(context)
    elapsed = time.monotonic() - started_at
    if elapsed > POLICY_TIMEOUT_SECONDS:
        return None
    return result


def _is_legal_intent(intent: EnemyIntent, legal_actions: tuple[LegalActionCandidate, ...]) -> bool:
    for action in legal_actions:
        if action.action_id != intent.action_id:
            continue
        return tuple(intent.target_ids) in action.target_combinations
    return False


async def _apply_damage(
    session: AsyncSession, run_id: uuid.UUID, result: DamageResult, *, now: datetime
) -> None:
    target_id = uuid.UUID(result.target_id)

    run_enemy_target = await session.get(RunEnemy, target_id)
    if run_enemy_target is not None and run_enemy_target.run_id == run_id:
        run_enemy_target.hp = max(0, run_enemy_target.hp - result.amount)
        if run_enemy_target.hp == 0 and run_enemy_target.defeated_at is None:
            run_enemy_target.defeated_at = now
        return

    adventurer_target = await session.get(RunAdventurer, target_id)
    if adventurer_target is not None and adventurer_target.run_id == run_id:
        adventurer_target.hp = max(0, adventurer_target.hp - result.amount)
        if adventurer_target.hp == 0:
            adventurer_target.is_alive = False
