from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from yt_live_dungeon.persistence.models import ProcessedCommand


async def test_rejects_duplicate_source_and_message_id(db_session, run_factory):
    run = await run_factory()
    received_at = datetime.now(UTC)

    db_session.add(
        ProcessedCommand(
            source="youtube_live",
            source_message_id="msg-1",
            run_id=run.id,
            viewer_id="viewer-1",
            raw_text="@ready",
            processed=True,
            received_at=received_at,
        )
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        db_session.add(
            ProcessedCommand(
                source="youtube_live",
                source_message_id="msg-1",
                run_id=run.id,
                viewer_id="viewer-1",
                raw_text="@ready",
                processed=True,
                received_at=received_at,
            )
        )
        await db_session.flush()


async def test_allows_same_message_id_from_different_source(db_session, run_factory):
    run = await run_factory()
    received_at = datetime.now(UTC)

    db_session.add(
        ProcessedCommand(
            source="youtube_live",
            source_message_id="msg-1",
            run_id=run.id,
            viewer_id="viewer-1",
            raw_text="@ready",
            processed=True,
            received_at=received_at,
        )
    )
    db_session.add(
        ProcessedCommand(
            source="unity",
            source_message_id="msg-1",
            run_id=run.id,
            viewer_id="viewer-1",
            raw_text="@ready",
            processed=True,
            received_at=received_at,
        )
    )
    await db_session.flush()
