from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.battle.context import EnemyDecisionContext, EnemyIntent


class RandomEnemyPolicy:
    """random_v1: selects uniformly at random from the Battle Engine's
    already-legal action/target-combination candidates. Never touches
    the DB or any runtime state, and never assembles a target
    combination of its own -- only ever returns one exactly as
    presented in `context.legal_actions`. Deterministic given its
    injected RandomSource.

    Assumes context.legal_actions is non-empty -- the Battle Engine
    never calls a Policy when there is nothing legal to do.
    """

    def __init__(self, random_source: RandomSource):
        self._random_source = random_source

    def decide(self, context: EnemyDecisionContext) -> EnemyIntent:
        action = self._random_source.sample(list(context.legal_actions), 1)[0]
        targets = self._random_source.sample(list(action.target_combinations), 1)[0]
        return EnemyIntent(action_id=action.action_id, target_ids=targets)
