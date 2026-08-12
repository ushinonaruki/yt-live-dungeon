import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from yt_live_dungeon.app import app
from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import Run


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def existing_run():
    async with async_session_factory() as session:
        run = Run()
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run
