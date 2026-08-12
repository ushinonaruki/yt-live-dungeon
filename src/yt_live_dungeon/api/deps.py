from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.database import async_session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
