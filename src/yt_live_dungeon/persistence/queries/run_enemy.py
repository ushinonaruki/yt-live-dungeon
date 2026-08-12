import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import Enemy, RunEnemy


async def list_floor_enemies(
    session: AsyncSession, run_id: uuid.UUID, floor: int, *, for_update: bool = False
) -> list[RunEnemy]:
    """All RunEnemy rows for one run's specific floor, ordered by
    order_in_group. Scoped to `floor` explicitly so a previous floor's
    (defeated or not) enemies never leak into a current-floor read."""
    stmt = (
        select(RunEnemy)
        .where(RunEnemy.run_id == run_id, RunEnemy.floor == floor)
        .order_by(RunEnemy.order_in_group)
    )
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_floor_enemies_with_master_data(
    session: AsyncSession, run_id: uuid.UUID, floor: int
) -> list[tuple[RunEnemy, Enemy]]:
    """(RunEnemy, Enemy) pairs for one run's specific floor, ordered by
    order_in_group -- used to build the state API's enemy DTOs, which
    need the Enemy's stable key/display name alongside the RunEnemy
    snapshot."""
    result = await session.execute(
        select(RunEnemy, Enemy)
        .join(Enemy, Enemy.id == RunEnemy.enemy_id)
        .where(RunEnemy.run_id == run_id, RunEnemy.floor == floor)
        .order_by(RunEnemy.order_in_group)
    )
    return list(result.all())


async def get_run_enemy(
    session: AsyncSession, run_enemy_id: uuid.UUID, *, for_update: bool = False
) -> RunEnemy | None:
    if for_update:
        return await session.get(RunEnemy, run_enemy_id, with_for_update=True)
    return await session.get(RunEnemy, run_enemy_id)
