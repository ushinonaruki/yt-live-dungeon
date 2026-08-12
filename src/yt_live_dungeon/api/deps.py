from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.database import async_session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


def get_current_time() -> datetime:
    """The FastAPI dependency boundary for "now" in routes, mirroring
    the `now: datetime` parameter every Use Case below the API layer
    already takes explicitly. Production resolves this to the real
    UTC clock; tests replace it via `app.dependency_overrides` for a
    fixed, reproducible instant -- no monkeypatching of this module or
    the route itself."""
    return datetime.now(UTC)
