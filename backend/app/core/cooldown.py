import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import redis.asyncio as aioredis


def cooldown_key(run_adventurer_id: UUID) -> str:
    return f"cooldown:adventurer:{run_adventurer_id}"


async def is_on_cooldown(redis: aioredis.Redis, run_adventurer_id: UUID) -> bool:
    return await redis.exists(cooldown_key(run_adventurer_id)) == 1


async def set_cooldown(
    redis: aioredis.Redis,
    run_adventurer_id: UUID,
    spell_name: str,
    cooldown_seconds: int,
) -> None:
    key = cooldown_key(run_adventurer_id)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    value = json.dumps({"spell_name": spell_name, "expires_at": expires_at})
    await redis.set(key, value, ex=cooldown_seconds)
