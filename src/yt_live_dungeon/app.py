from fastapi import FastAPI

from yt_live_dungeon.api import command_routes, health_routes, run_routes, state_routes

app = FastAPI(title="YT Live Dungeon API")

app.include_router(health_routes.router)
app.include_router(run_routes.router)
app.include_router(command_routes.router)
app.include_router(state_routes.router)
