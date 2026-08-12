from collections.abc import Callable

from yt_live_dungeon.domain.random_source import RandomSource
from yt_live_dungeon.features.battle.context import EnemyPolicy
from yt_live_dungeon.features.battle.policies.random_v1 import RandomEnemyPolicy

PolicyFactory = Callable[[RandomSource], EnemyPolicy]

_REGISTRY: dict[str, PolicyFactory] = {
    "random_v1": RandomEnemyPolicy,
}


def resolve_policy(policy_key: str, random_source: RandomSource) -> EnemyPolicy | None:
    """The Battle Engine resolves an Enemy's ai_policy_key through this
    registry alone -- it never branches on policy_key itself. Returns
    None for an unregistered key so the caller can fall back rather than
    letting one enemy's bad master-data config crash a whole floor's
    combat; it is not this function's job to decide what "unregistered"
    should do.
    """
    factory = _REGISTRY.get(policy_key)
    if factory is None:
        return None
    return factory(random_source)
