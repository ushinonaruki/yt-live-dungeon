import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import ProcessedCommand


def _payload(**overrides):
    payload = {
        "source": "youtube_live",
        "source_message_id": "message-1",
        "viewer_id": "viewer-1",
        "viewer_display_name": "Viewer One",
        "raw_text": "@ready",
        "received_at": datetime.now(UTC).isoformat(),
    }
    payload.update(overrides)
    return payload


async def _processed_command_count(source: str, source_message_id: str) -> int:
    async with async_session_factory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(ProcessedCommand)
            .where(
                ProcessedCommand.source == source,
                ProcessedCommand.source_message_id == source_message_id,
            )
        )
        return result.scalar_one()


async def test_invalid_syntax_command_is_recorded_as_invalid_syntax(client, existing_run):
    response = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands",
        json=_payload(source_message_id="message-2", raw_text="not a command"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"processed": False, "reason": "invalid_syntax", "result": None}


async def test_command_for_nonexistent_run_returns_404(client):
    missing_run_id = uuid.uuid4()

    response = await client.post(
        f"/api/v1/runs/{missing_run_id}/commands", json=_payload(source_message_id="message-3")
    )

    assert response.status_code == 404


async def test_duplicate_source_message_id_is_not_double_processed(client, existing_run):
    payload = _payload(source_message_id="message-dup")

    first = await client.post(f"/api/v1/runs/{existing_run.id}/commands", json=payload)
    second = await client.post(f"/api/v1/runs/{existing_run.id}/commands", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    count = await _processed_command_count("youtube_live", "message-dup")
    assert count == 1


async def test_same_source_message_id_allowed_across_different_sources(client, existing_run):
    shared_message_id = "shared-message-id"

    from_youtube = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands",
        json=_payload(source="youtube_live", source_message_id=shared_message_id),
    )
    from_unity = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands",
        json=_payload(source="unity", source_message_id=shared_message_id),
    )

    assert from_youtube.status_code == 200
    assert from_unity.status_code == 200

    youtube_count = await _processed_command_count("youtube_live", shared_message_id)
    unity_count = await _processed_command_count("unity", shared_message_id)
    assert youtube_count == 1
    assert unity_count == 1


async def test_empty_source_is_rejected_with_422(client, existing_run):
    response = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands", json=_payload(source="")
    )

    assert response.status_code == 422


async def test_source_over_32_chars_is_rejected_with_422(client, existing_run):
    response = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands", json=_payload(source="x" * 33)
    )

    assert response.status_code == 422


async def test_source_at_32_chars_is_accepted(client, existing_run):
    response = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands",
        json=_payload(source="x" * 32, source_message_id="boundary-source"),
    )

    assert response.status_code == 200


async def test_source_message_id_over_256_chars_is_rejected_with_422(client, existing_run):
    response = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands",
        json=_payload(source_message_id="x" * 257),
    )

    assert response.status_code == 422


async def test_empty_source_message_id_is_rejected_with_422(client, existing_run):
    response = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands", json=_payload(source_message_id="")
    )

    assert response.status_code == 422


async def test_empty_viewer_id_is_rejected_with_422(client, existing_run):
    response = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands", json=_payload(viewer_id="")
    )

    assert response.status_code == 422


async def test_viewer_id_over_256_chars_is_rejected_with_422(client, existing_run):
    response = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands", json=_payload(viewer_id="x" * 257)
    )

    assert response.status_code == 422


async def test_naive_received_at_is_rejected_with_422(client, existing_run):
    response = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands",
        json=_payload(
            source_message_id="naive-datetime",
            received_at=datetime.now().isoformat(),  # noqa: DTZ005 -- deliberately naive
        ),
    )

    assert response.status_code == 422


async def test_empty_raw_text_is_accepted_and_recorded_as_invalid_syntax(client, existing_run):
    response = await client.post(
        f"/api/v1/runs/{existing_run.id}/commands",
        json=_payload(source_message_id="empty-raw-text", raw_text=""),
    )

    assert response.status_code == 200
    assert response.json() == {"processed": False, "reason": "invalid_syntax", "result": None}
