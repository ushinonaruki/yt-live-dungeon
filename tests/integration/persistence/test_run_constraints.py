import pytest
from sqlalchemy.exc import IntegrityError


async def test_rejects_duplicate_viewer_in_same_run(db_session, run_factory, adventurer_factory):
    run = await run_factory()
    await adventurer_factory(run_id=run.id, youtube_id="same_viewer")

    with pytest.raises(IntegrityError):
        await adventurer_factory(run_id=run.id, youtube_id="same_viewer")


async def test_allows_same_viewer_in_different_runs(db_session, run_factory, adventurer_factory):
    run_a = await run_factory()
    run_b = await run_factory()

    await adventurer_factory(run_id=run_a.id, youtube_id="same_viewer")
    adventurer_b = await adventurer_factory(run_id=run_b.id, youtube_id="same_viewer")

    assert adventurer_b.id is not None
