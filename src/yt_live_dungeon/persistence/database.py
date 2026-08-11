from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from yt_live_dungeon.config import settings

engine: AsyncEngine = create_async_engine(settings.database_url)


async def ping() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
