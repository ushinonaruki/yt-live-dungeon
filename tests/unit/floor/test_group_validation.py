import pytest

from yt_live_dungeon.domain.errors import EnemyGroupConfigurationError
from yt_live_dungeon.features.floor.group_validation import (
    GroupMemberSpec,
    validate_group_composition,
)


def test_accepts_master_only_group():
    validate_group_composition([GroupMemberSpec(order_in_group=1, role="master")])


def test_accepts_master_plus_eight_minions():
    members = [GroupMemberSpec(order_in_group=1, role="master")] + [
        GroupMemberSpec(order_in_group=i, role="minion") for i in range(2, 10)
    ]
    validate_group_composition(members)


def test_rejects_empty_group():
    with pytest.raises(EnemyGroupConfigurationError):
        validate_group_composition([])


def test_rejects_multiple_masters():
    members = [
        GroupMemberSpec(order_in_group=1, role="master"),
        GroupMemberSpec(order_in_group=2, role="master"),
    ]
    with pytest.raises(EnemyGroupConfigurationError):
        validate_group_composition(members)


def test_rejects_no_master():
    members = [GroupMemberSpec(order_in_group=1, role="minion")]
    with pytest.raises(EnemyGroupConfigurationError):
        validate_group_composition(members)


def test_rejects_nine_minions_plus_a_master():
    members = [GroupMemberSpec(order_in_group=1, role="master")] + [
        GroupMemberSpec(order_in_group=i, role="minion") for i in range(2, 11)
    ]
    with pytest.raises(EnemyGroupConfigurationError):
        validate_group_composition(members)


def test_rejects_duplicate_order_in_group():
    members = [
        GroupMemberSpec(order_in_group=1, role="master"),
        GroupMemberSpec(order_in_group=1, role="minion"),
    ]
    with pytest.raises(EnemyGroupConfigurationError):
        validate_group_composition(members)


def test_rejects_non_contiguous_order_in_group():
    members = [
        GroupMemberSpec(order_in_group=1, role="master"),
        GroupMemberSpec(order_in_group=3, role="minion"),
    ]
    with pytest.raises(EnemyGroupConfigurationError):
        validate_group_composition(members)


def test_rejects_invalid_role():
    members = [GroupMemberSpec(order_in_group=1, role="boss")]
    with pytest.raises(EnemyGroupConfigurationError):
        validate_group_composition(members)
