from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.domain.attributes import validate_attribute_dict
from yt_live_dungeon.domain.errors import EnemyGroupConfigurationError, InvalidParticipantCountError
from yt_live_dungeon.features.floor.scaling import calculate_enemy_floor_stats
from yt_live_dungeon.persistence.models import RunEnemy
from yt_live_dungeon.persistence.queries.adventurer import list_active_participants
from yt_live_dungeon.persistence.queries.enemy_group import list_group_members

# obsidian/.../キャラクター/ステータス.md section 8 and
# ダンジョン/フロア補正.md section 5: base MP natural-regen rate for
# every combatant is 1 MP/sec; enemies multiply it by the floor-start
# participant count (see BASE_MP_REGEN_PER_SECOND usage below).
BASE_MP_REGEN_PER_SECOND = 1

# 進行/キャンプ.md's 8-person CAMP participant cap, mirrored here as
# this table's hard floor-start invariant: 1 <= n <= 8.
MIN_PARTICIPANTS_TO_SPAWN = 1
MAX_PARTICIPANTS_TO_SPAWN = 8


async def spawn_group(
    session: AsyncSession,
    run_id,
    floor: int,
    group_id: int,
    *,
    now: datetime,
) -> list[RunEnemy]:
    """Expands `group_id`'s fixed, pre-registered composition into
    RunEnemy rows for `run_id`'s `floor`: floor-scaled max HP and
    10-attributes (current HP/MP start at their respective max), role,
    and order copied verbatim from the group's registered members. No
    master/minion count or species is drawn here -- the group's already
    -validated composition is expanded as-is.

    Each spawned enemy's MP natural-regen rate is snapshotted here, once,
    from the currently participating-and-alive adventurer count at this
    exact moment (obsidian/.../ダンジョン/フロア補正.md section 5). Only
    the master's rate is multiplied by that participant count -- every
    minion keeps the base rate regardless of participant count, per the
    same section. Role is read from each member's own registered role
    (never array position), so this holds regardless of a group's
    member ordering. Neither rate changes afterward even if participants
    later log out or die. `now` anchors the regen clock
    (mp_regen_updated_at); it is otherwise unused here.

    Never commits/rollbacks -- the caller owns the transaction.

    Raises EnemyGroupConfigurationError before adding anything if the
    referenced group has no members or is missing its master -- this
    should never happen for a properly registered group, but a corrupt
    or incomplete group must never be silently expanded.

    Raises InvalidParticipantCountError before adding anything if the
    floor-start participant count is outside 1-8. This is a hard
    runtime invariant, not a soft default: a caller that can legitimately
    reach 0 participants (e.g. CAMP ending with nobody left) must branch
    to RETIRE or equivalent *before* ever calling this function -- it is
    never this function's job to spawn a battle-less floor or silently
    treat 0 participants as "no regen bonus."
    """
    members = await list_group_members(session, group_id)
    if not members:
        raise EnemyGroupConfigurationError(f"group {group_id} has no members")

    master_count = sum(1 for member, _enemy in members if member.role == "master")
    if master_count != 1:
        raise EnemyGroupConfigurationError(
            f"group {group_id} must have exactly one master, has {master_count}"
        )

    participant_count = len(await list_active_participants(session, run_id))
    if not (MIN_PARTICIPANTS_TO_SPAWN <= participant_count <= MAX_PARTICIPANTS_TO_SPAWN):
        raise InvalidParticipantCountError(
            f"run {run_id} has {participant_count} active participants at floor "
            f"{floor} start; must be between {MIN_PARTICIPANTS_TO_SPAWN} and "
            f"{MAX_PARTICIPANTS_TO_SPAWN}"
        )
    master_mp_regen_rate = BASE_MP_REGEN_PER_SECOND * participant_count

    run_enemies = []
    for member, enemy in members:
        stats = calculate_enemy_floor_stats(enemy.base_max_hp, enemy.base_attributes, floor)
        validate_attribute_dict(stats.attributes)

        mp_regen_rate = (
            master_mp_regen_rate if member.role == "master" else BASE_MP_REGEN_PER_SECOND
        )

        run_enemy = RunEnemy(
            run_id=run_id,
            floor=floor,
            group_id=group_id,
            enemy_id=enemy.id,
            order_in_group=member.order_in_group,
            role=member.role,
            max_hp=stats.max_hp,
            hp=stats.max_hp,
            max_mp=enemy.base_max_mp,
            mp=enemy.base_max_mp,
            mp_regen_rate=mp_regen_rate,
            mp_regen_updated_at=now,
            attributes=stats.attributes,
            defeated_at=None,
        )
        session.add(run_enemy)
        run_enemies.append(run_enemy)

    return run_enemies
