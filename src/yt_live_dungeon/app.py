from fastapi import FastAPI

from yt_live_dungeon.api import health_routes

app = FastAPI(title="YT Live Dungeon API")

app.include_router(health_routes.router)
