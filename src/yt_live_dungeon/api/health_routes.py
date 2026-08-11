from fastapi import APIRouter, Response

from yt_live_dungeon.cache import redis as redis_cache
from yt_live_dungeon.persistence import database

router = APIRouter()


@router.get("/health")
async def health(response: Response) -> dict:
    checks = {"database": "ok", "redis": "ok"}

    try:
        await database.ping()
    except Exception:
        checks["database"] = "error"

    try:
        await redis_cache.ping()
    except Exception:
        checks["redis"] = "error"

    status = "ok" if all(value == "ok" for value in checks.values()) else "error"
    if status != "ok":
        response.status_code = 503

    return {"status": status, **checks}
