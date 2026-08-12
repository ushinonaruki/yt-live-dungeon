from dataclasses import dataclass

from yt_live_dungeon.domain.errors import EnemyGroupConfigurationError

MAX_GROUP_MEMBERS = 9
MAX_MINIONS = 8
VALID_ROLES = ("master", "minion")


@dataclass(frozen=True)
class GroupMemberSpec:
    order_in_group: int
    role: str


def validate_group_composition(members: list[GroupMemberSpec]) -> None:
    """A legal EnemyGroup composition: exactly one master, 0-8 minions,
    no other roles, and order_in_group values forming a contiguous,
    duplicate-free 1..N range. Used before registering a group (e.g. by
    the seed loader) so an incomplete or malformed group can never reach
    the database in the first place -- draw/spawn time then never needs
    to reject a group for these reasons.
    """
    if not members:
        raise EnemyGroupConfigurationError("group must have at least one member")
    if len(members) > MAX_GROUP_MEMBERS:
        raise EnemyGroupConfigurationError(
            f"group has {len(members)} members, at most {MAX_GROUP_MEMBERS} allowed"
        )

    invalid_roles = {member.role for member in members} - set(VALID_ROLES)
    if invalid_roles:
        raise EnemyGroupConfigurationError(f"invalid role(s): {sorted(invalid_roles)}")

    master_count = sum(1 for member in members if member.role == "master")
    if master_count != 1:
        raise EnemyGroupConfigurationError(
            f"group must have exactly one master, has {master_count}"
        )

    minion_count = sum(1 for member in members if member.role == "minion")
    if minion_count > MAX_MINIONS:
        raise EnemyGroupConfigurationError(
            f"group has {minion_count} minions, at most {MAX_MINIONS} allowed"
        )

    orders = [member.order_in_group for member in members]
    if len(set(orders)) != len(orders):
        raise EnemyGroupConfigurationError("order_in_group values must be unique")
    if sorted(orders) != list(range(1, len(members) + 1)):
        raise EnemyGroupConfigurationError(
            "order_in_group values must form a contiguous 1..N range"
        )
