from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.config import settings


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
