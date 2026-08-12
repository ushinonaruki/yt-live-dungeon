from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import ProcessedCommand


async def find_by_source_and_message_id(
    session: AsyncSession, source: str, source_message_id: str
) -> ProcessedCommand | None:
    result = await session.execute(
        select(ProcessedCommand).where(
            ProcessedCommand.source == source,
            ProcessedCommand.source_message_id == source_message_id,
        )
    )
    return result.scalar_one_or_none()
