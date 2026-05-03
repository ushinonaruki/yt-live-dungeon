from fastapi import FastAPI

app = FastAPI(title="YT Live Dungeon API")


@app.get("/health")
async def health():
    return {"status": "ok"}
