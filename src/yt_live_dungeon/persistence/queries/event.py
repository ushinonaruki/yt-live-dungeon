import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import RunEvent


async def list_events_after(
    session: AsyncSession, run_id: uuid.UUID, after: int
) -> list[RunEvent]:
    result = await session.execute(
        select(RunEvent)
        .where(RunEvent.run_id == run_id, RunEvent.sequence > after)
        .order_by(RunEvent.sequence.asc())
    )
    return list(result.scalars().all())
