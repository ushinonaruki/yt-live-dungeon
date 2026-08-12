import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import Run


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> Run | None:
    return await session.get(Run, run_id)
