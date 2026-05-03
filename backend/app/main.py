from fastapi import FastAPI

from app.api.routes import commands, runs

app = FastAPI(title="YT Live Dungeon API")


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(runs.router)
app.include_router(commands.router)
