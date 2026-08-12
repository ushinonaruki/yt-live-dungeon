from dataclasses import dataclass

from yt_live_dungeon.features.battle.context import CombatantSnapshot


@dataclass(frozen=True)
class DamageResult:
    target_id: str
    amount: int


def calculate_damage(
    attacker: CombatantSnapshot, target: CombatantSnapshot, *, attribute: str, base_power: int
) -> int:
    """Basic Damage, per obsidian/YTL100ダンジョン/戦闘システム/Damage.md:

    Damage = max(0, base_power + attacker[attribute] - target[attribute])

    The Weak multiplier (normally applied to base_power) and Chain
    multiplier (normally applied to the whole result) are both
    unimplemented in this commit -- Weak/Chain/Break/Intercept are
    explicitly out of scope for Commit 7 -- so this is the formula with
    both left at their neutral values (1x), not an approximation of it.
    """
    attacker_value = attacker.attributes.get(attribute, 0)
    target_value = target.attributes.get(attribute, 0)
    return max(0, base_power + attacker_value - target_value)


def resolve_damage_effect(
    attacker: CombatantSnapshot, targets: list[CombatantSnapshot], params: dict
) -> list[DamageResult]:
    attribute = params["attribute"]
    base_power = params["base_power"]
    return [
        DamageResult(
            target_id=target.combatant_id,
            amount=calculate_damage(attacker, target, attribute=attribute, base_power=base_power),
        )
        for target in targets
    ]


def resolve_effects(
    attacker: CombatantSnapshot, targets: list[CombatantSnapshot], effects: list[dict]
) -> list[DamageResult]:
    """Processes a Spell's `effects` list, in definition order, per
    obsidian/YTL100ダンジョン/呪文/呪文定義仕様.md's effect_id/params
    shape (`{"effect_id": "damage", "effect_target": "selected_targets",
    "params": {"attribute": ..., "base_power": ..., "hit_count": ...}}`).

    Only effect_id == "damage" is implemented: it is the only effect any
    currently-defined enemy Spell actually uses, and
    obsidian/.../呪文系統.md is explicit that new Effects should only be
    added once they're actually needed. Any other effect_id raises
    rather than silently doing nothing, since silently skipping a
    Spell's defined behavior would be worse than failing loudly.
    """
    results: list[DamageResult] = []
    for effect in effects:
        effect_id = effect["effect_id"]
        if effect_id == "damage":
            results.extend(resolve_damage_effect(attacker, targets, effect["params"]))
        else:
            raise NotImplementedError(f"unsupported effect_id: {effect_id!r}")
    return results
