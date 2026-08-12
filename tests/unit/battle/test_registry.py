import random

from yt_live_dungeon.features.battle.policies.random_v1 import RandomEnemyPolicy
from yt_live_dungeon.features.battle.registry import resolve_policy


def test_resolves_random_v1_to_random_enemy_policy():
    policy = resolve_policy("random_v1", random.Random(1))

    assert isinstance(policy, RandomEnemyPolicy)


def test_returns_none_for_an_unregistered_key():
    policy = resolve_policy("does_not_exist_v99", random.Random(1))

    assert policy is None
