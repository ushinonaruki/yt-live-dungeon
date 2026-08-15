from sqlalchemy import select

from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import RunEnemy


async def test_create_run_returns_waiting_state(client):
    response = await client.post("/api/v1/runs")

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "waiting"
    assert body["current_floor"] == 1


async def test_create_run_waiting_deadline_is_none_until_first_login(client):
    response = await client.post("/api/v1/runs")

    body = response.json()
    assert body["waiting_deadline_at"] is None


async def test_create_run_spawns_no_enemies(client):
    response = await client.post("/api/v1/runs")
    run_id = response.json()["id"]

    async with async_session_factory() as session:
        spawned = (
            await session.execute(select(RunEnemy).where(RunEnemy.run_id == run_id))
        ).scalars().all()
    assert spawned == []


async def test_create_run_is_visible_through_state_endpoint(client):
    created = await client.post("/api/v1/runs")
    run_id = created.json()["id"]

    response = await client.get(f"/api/v1/runs/{run_id}/state")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "waiting"
    assert body["enemies"] == []
    assert body["camp"] is None
