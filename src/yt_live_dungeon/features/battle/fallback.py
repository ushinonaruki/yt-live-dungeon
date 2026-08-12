from yt_live_dungeon.features.battle.context import EnemyDecisionContext, EnemyIntent


class DeterministicFallbackPolicy:
    """Picks the first legal action (by action_id) and, within it, its
    first legal target combination (by stable tuple ordering) -- both
    already presented as legal by the Battle Engine.

    Used only by the Battle Engine itself, whenever the registered
    policy key doesn't resolve, the policy raises, appears to hang, or
    returns an Intent that fails re-validation. Never registered under a
    policy_key and never selected by name.

    Assumes context.legal_actions is non-empty, same as any EnemyPolicy.
    """

    def decide(self, context: EnemyDecisionContext) -> EnemyIntent:
        action = min(context.legal_actions, key=lambda candidate: candidate.action_id)
        target_combination = min(action.target_combinations)
        return EnemyIntent(action_id=action.action_id, target_ids=target_combination)
