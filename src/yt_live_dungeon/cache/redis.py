from redis.asyncio import Redis

from yt_live_dungeon.config import settings

redis_client: Redis = Redis.from_url(settings.redis_url)


async def ping() -> None:
    await redis_client.ping()
