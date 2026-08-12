from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import Enemy, EnemyGroup, EnemyGroupMember


async def list_active_group_ids(session: AsyncSession) -> list[int]:
    """Active group ids, ordered by id for a deterministic draw
    population (a seeded RandomSource.sample() must not depend on
    Postgres's unspecified physical row order)."""
    result = await session.execute(
        select(EnemyGroup.id).where(EnemyGroup.is_active.is_(True)).order_by(EnemyGroup.id)
    )
    return list(result.scalars().all())


async def get_group(session: AsyncSession, group_id: int) -> EnemyGroup | None:
    return await session.get(EnemyGroup, group_id)


async def list_group_members(
    session: AsyncSession, group_id: int
) -> list[tuple[EnemyGroupMember, Enemy]]:
    """(EnemyGroupMember, Enemy) pairs for a group, ordered by
    order_in_group (the group's fixed composition order)."""
    result = await session.execute(
        select(EnemyGroupMember, Enemy)
        .join(Enemy, Enemy.id == EnemyGroupMember.enemy_id)
        .where(EnemyGroupMember.group_id == group_id)
        .order_by(EnemyGroupMember.order_in_group)
    )
    return list(result.all())
