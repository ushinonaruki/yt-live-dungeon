import pytest

from yt_live_dungeon.features.battle.context import CombatantSnapshot
from yt_live_dungeon.features.battle.effects import calculate_damage, resolve_effects


def _combatant(**overrides) -> CombatantSnapshot:
    defaults = dict(
        combatant_id="c1",
        kind="enemy",
        display_name="test",
        role=None,
        hp=100,
        max_hp=100,
        mp=20,
        max_mp=20,
        attributes={"rr": 0},
        is_alive=True,
    )
    defaults.update(overrides)
    return CombatantSnapshot(**defaults)


def test_damage_is_base_power_plus_attacker_attribute_minus_target_attribute():
    attacker = _combatant(combatant_id="a", attributes={"rr": 10})
    target = _combatant(combatant_id="t", attributes={"rr": 3})

    damage = calculate_damage(attacker, target, attribute="rr", base_power=5)

    assert damage == 5 + 10 - 3


def test_damage_is_clamped_at_zero_when_formula_goes_negative():
    attacker = _combatant(combatant_id="a", attributes={"rr": 0})
    target = _combatant(combatant_id="t", attributes={"rr": 1000})

    damage = calculate_damage(attacker, target, attribute="rr", base_power=5)

    assert damage == 0


def test_damage_defaults_missing_attribute_keys_to_zero():
    attacker = _combatant(combatant_id="a", attributes={})
    target = _combatant(combatant_id="t", attributes={})

    damage = calculate_damage(attacker, target, attribute="rr", base_power=7)

    assert damage == 7


def test_resolve_effects_applies_damage_to_every_target():
    attacker = _combatant(combatant_id="a", attributes={"rr": 5})
    target_1 = _combatant(combatant_id="t1", attributes={"rr": 0})
    target_2 = _combatant(combatant_id="t2", attributes={"rr": 2})
    effects = [
        {
            "effect_id": "damage",
            "effect_target": "selected_targets",
            "params": {"attribute": "rr", "base_power": 5, "hit_count": 1},
        }
    ]

    results = resolve_effects(attacker, [target_1, target_2], effects)

    by_target = {r.target_id: r.amount for r in results}
    assert by_target == {"t1": 10, "t2": 8}


def test_resolve_effects_raises_for_an_unsupported_effect_id():
    attacker = _combatant(combatant_id="a")
    target = _combatant(combatant_id="t")
    effects = [
        {"effect_id": "status_accumulate", "effect_target": "selected_targets", "params": {}}
    ]

    with pytest.raises(NotImplementedError):
        resolve_effects(attacker, [target], effects)
