import pytest
from sqlalchemy.exc import IntegrityError

from yt_live_dungeon.persistence.models import RunEvent


async def test_event_sequence_unique_within_run(db_session, run_factory):
    run = await run_factory()

    db_session.add(RunEvent(run_id=run.id, sequence=1, event_type="camp_started", body={}))
    await db_session.flush()

    with pytest.raises(IntegrityError):
        db_session.add(RunEvent(run_id=run.id, sequence=1, event_type="camp_ended", body={}))
        await db_session.flush()


async def test_same_sequence_allowed_in_different_runs(db_session, run_factory):
    run_a = await run_factory()
    run_b = await run_factory()

    db_session.add(RunEvent(run_id=run_a.id, sequence=1, event_type="camp_started", body={}))
    db_session.add(RunEvent(run_id=run_b.id, sequence=1, event_type="camp_started", body={}))
    await db_session.flush()
