import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.mp_regen import apply_mp_regen
from yt_live_dungeon.features.adventurer.stats import calculate_final_stats
from yt_live_dungeon.features.battle.context import CombatantSnapshot, LegalActionCandidate
from yt_live_dungeon.persistence.models import RunAdventurer, RunEnemy
from yt_live_dungeon.persistence.queries.adventurer import list_active_participants
from yt_live_dungeon.persistence.queries.enemy import get_enemy, list_enemy_spells
from yt_live_dungeon.persistence.queries.inventory import list_owned_rows, to_inventory_entries
from yt_live_dungeon.persistence.queries.run_enemy import list_floor_enemies

# target_rule is resolved relative to the *caster's* faction, uniformly
# for adventurer- and enemy-cast spells alike (see obsidian/.../
# 呪文/呪文定義仕様.md section 7 and 戦闘システム/対象解決.md section 2):
# "enemies" is always the opposing faction, "allies" the caster's own.
# All three non-"none" rules currently mean "pick exactly 1 living
# combatant from the named pool" -- 対象解決.md never describes a
# multi-target rule, so no combination-generation beyond singletons is
# implemented here.
TARGET_RULE_NONE = "none"
TARGET_RULE_ENEMIES = "enemies"
TARGET_RULE_ALLIES = "allies"
TARGET_RULE_ALL = "all"


def _enemy_snapshot(run_enemy: RunEnemy, display_name: str, *, now: datetime) -> CombatantSnapshot:
    """mp is a pure, read-only projection to `now` via the enemy's
    stored mp_regen_rate/mp_regen_updated_at -- never the raw DB column
    verbatim, and this never writes back to `run_enemy`. This applies
    uniformly to every enemy snapshot (the acting enemy and its
    still-living floor-mates alike): whichever RunEnemy actually gets
    picked to act is the only one resolve_enemy_action() persists
    catch-up onto, but every enemy's *displayed* mp here reflects the
    same instant either way, so a Policy never sees a stale ally MP."""
    regen = apply_mp_regen(
        mp=run_enemy.mp,
        max_mp=run_enemy.max_mp,
        regen_rate=run_enemy.mp_regen_rate,
        updated_at=run_enemy.mp_regen_updated_at,
        now=now,
    )
    return CombatantSnapshot(
        combatant_id=str(run_enemy.id),
        kind="enemy",
        display_name=display_name,
        role=run_enemy.role,
        hp=run_enemy.hp,
        max_hp=run_enemy.max_hp,
        mp=regen.mp,
        max_mp=run_enemy.max_mp,
        attributes=dict(run_enemy.attributes),
        is_alive=run_enemy.defeated_at is None,
    )


async def _adventurer_snapshot(
    session: AsyncSession, adventurer: RunAdventurer
) -> CombatantSnapshot:
    rows = await list_owned_rows(session, adventurer.id)
    entries = to_inventory_entries(rows)
    stats = calculate_final_stats(adventurer.base_max_hp, entries)
    return CombatantSnapshot(
        combatant_id=str(adventurer.id),
        kind="adventurer",
        display_name=adventurer.youtube_id,
        role=None,
        hp=adventurer.hp,
        max_hp=stats.max_hp,
        mp=adventurer.mp,
        max_mp=stats.max_mp,
        attributes=stats.attributes,
        is_alive=adventurer.is_alive,
    )


@dataclass(frozen=True)
class FloorCombatants:
    actor: CombatantSnapshot
    allies: tuple[CombatantSnapshot, ...]
    enemies: tuple[CombatantSnapshot, ...]


async def build_floor_combatants(
    session: AsyncSession,
    run_id: uuid.UUID,
    floor: int,
    actor_run_enemy: RunEnemy,
    *,
    now: datetime,
) -> FloorCombatants:
    """Snapshots for one enemy's decision: itself, its still-living
    floor-mates (allies), and the still-living, currently-participating
    adventurers (enemies, from this actor's perspective). Only the given
    `floor` is read -- a previous floor's RunEnemy rows never leak in.

    Every enemy snapshot's mp (actor's own included) is projected to
    `now` via _enemy_snapshot() without mutating any RunEnemy row --
    persisting the actor's catch-up, if any, is resolve_enemy_action()'s
    job, done only once it knows an action is actually being taken.
    """
    floor_enemy_rows = await list_floor_enemies(session, run_id, floor)

    actor_enemy_master = await get_enemy(session, actor_run_enemy.enemy_id)
    actor_snapshot = _enemy_snapshot(actor_run_enemy, actor_enemy_master.display_name, now=now)

    allies = []
    for row in floor_enemy_rows:
        if row.id == actor_run_enemy.id or row.defeated_at is not None:
            continue
        enemy_master = await get_enemy(session, row.enemy_id)
        allies.append(_enemy_snapshot(row, enemy_master.display_name, now=now))

    participants = await list_active_participants(session, run_id)
    enemies = [await _adventurer_snapshot(session, adventurer) for adventurer in participants]

    return FloorCombatants(
        actor=actor_snapshot, allies=tuple(allies), enemies=tuple(enemies)
    )


def _target_pool(target_rule: str, allies: tuple, enemies: tuple) -> list[CombatantSnapshot]:
    if target_rule == TARGET_RULE_ALLIES:
        return [c for c in allies if c.is_alive]
    if target_rule == TARGET_RULE_ENEMIES:
        return [c for c in enemies if c.is_alive]
    if target_rule == TARGET_RULE_ALL:
        return [c for c in (*allies, *enemies) if c.is_alive]
    return []


async def build_legal_actions(
    session: AsyncSession, actor_run_enemy: RunEnemy, combatants: FloorCombatants
) -> tuple[LegalActionCandidate, ...]:
    """Every Spell the actor can afford, paired with every legal
    single-target combination for it (or the single empty combination
    for target_rule == "none"). A Spell with zero legal target
    combinations is omitted entirely -- the Battle Engine never offers
    an action with no valid way to use it.

    Affordability is checked against combatants.actor.mp -- the same
    already-projected-to-`now` value the Policy's Context will show --
    not actor_run_enemy.mp, which may still be a stale, un-caught-up DB
    value at this point in the call (see resolve_enemy_action()).
    """
    spells = await list_enemy_spells(session, actor_run_enemy.enemy_id)
    candidates = []
    for spell in spells:
        if spell.mp_cost > combatants.actor.mp:
            continue

        if spell.target_rule == TARGET_RULE_NONE:
            combinations: tuple[tuple[str, ...], ...] = ((),)
        else:
            pool = _target_pool(spell.target_rule, combatants.allies, combatants.enemies)
            if not pool:
                continue
            combinations = tuple((c.combatant_id,) for c in pool)

        candidates.append(
            LegalActionCandidate(
                action_id=spell.id,
                command=spell.command,
                mp_cost=spell.mp_cost,
                target_rule=spell.target_rule,
                target_combinations=combinations,
            )
        )
    return tuple(candidates)
