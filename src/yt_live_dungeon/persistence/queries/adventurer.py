import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import RunAdventurer


async def get_adventurer_by_viewer(
    session: AsyncSession, run_id: uuid.UUID, youtube_id: str, *, for_update: bool = False
) -> RunAdventurer | None:
    stmt = select(RunAdventurer).where(
        RunAdventurer.run_id == run_id, RunAdventurer.youtube_id == youtube_id
    )
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_active_participants(
    session: AsyncSession, run_id: uuid.UUID
) -> list[RunAdventurer]:
    result = await session.execute(
        select(RunAdventurer).where(
            RunAdventurer.run_id == run_id,
            RunAdventurer.is_alive.is_(True),
            RunAdventurer.is_participating.is_(True),
        )
    )
    return list(result.scalars().all())
