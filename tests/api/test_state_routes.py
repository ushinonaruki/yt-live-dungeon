import uuid

from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import RunEvent


async def _add_event(
    run_id, sequence: int, event_type: str = "camp_started", body: dict | None = None
):
    async with async_session_factory() as session:
        session.add(
            RunEvent(run_id=run_id, sequence=sequence, event_type=event_type, body=body or {})
        )
        await session.commit()


async def test_get_state_returns_run_fields(client, existing_run):
    response = await client.get(f"/api/v1/runs/{existing_run.id}/state")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(existing_run.id)
    assert body["state"] == "waiting"
    assert body["current_floor"] == 1
    assert body["ended_at"] is None
    assert "started_at" in body
    assert body["camp"] is None


async def test_get_state_for_missing_run_returns_404(client):
    response = await client.get(f"/api/v1/runs/{uuid.uuid4()}/state")

    assert response.status_code == 404


async def test_get_events_with_no_events_returns_empty_list(client, existing_run):
    response = await client.get(f"/api/v1/runs/{existing_run.id}/events")

    assert response.status_code == 200
    assert response.json() == {"events": []}


async def test_get_events_returns_events_in_ascending_sequence_order(client, existing_run):
    await _add_event(existing_run.id, sequence=2, event_type="camp_ended")
    await _add_event(existing_run.id, sequence=1, event_type="camp_started")
    await _add_event(existing_run.id, sequence=3, event_type="run_retired")

    response = await client.get(f"/api/v1/runs/{existing_run.id}/events")

    assert response.status_code == 200
    events = response.json()["events"]
    assert [event["sequence"] for event in events] == [1, 2, 3]
    assert [event["event_type"] for event in events] == [
        "camp_started",
        "camp_ended",
        "run_retired",
    ]


async def test_get_events_after_filters_out_earlier_sequences(client, existing_run):
    await _add_event(existing_run.id, sequence=1, event_type="camp_started")
    await _add_event(existing_run.id, sequence=2, event_type="camp_ended")

    response = await client.get(f"/api/v1/runs/{existing_run.id}/events", params={"after": 1})

    assert response.status_code == 200
    events = response.json()["events"]
    assert [event["sequence"] for event in events] == [2]


async def test_get_events_for_missing_run_returns_404(client):
    response = await client.get(f"/api/v1/runs/{uuid.uuid4()}/events")

    assert response.status_code == 404
