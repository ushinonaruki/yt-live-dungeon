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


async def test_accepts_base_max_mp_of_100(run_factory, adventurer_factory):
    run = await run_factory()
    adventurer = await adventurer_factory(run_id=run.id, base_max_mp=100)
    assert adventurer.id is not None


async def test_rejects_base_max_mp_other_than_100(db_session, run_factory, adventurer_factory):
    """Per obsidian/.../キャラクター/ステータス.md section 5: max MP is
    fixed at 100 for every combatant, never adjustable by items."""
    run = await run_factory()
    with pytest.raises(IntegrityError):
        await adventurer_factory(run_id=run.id, base_max_mp=150)


async def test_rejects_negative_mp(db_session, run_factory, adventurer_factory):
    run = await run_factory()
    with pytest.raises(IntegrityError):
        await adventurer_factory(run_id=run.id, mp=-1)


async def test_rejects_mp_above_100(db_session, run_factory, adventurer_factory):
    run = await run_factory()
    with pytest.raises(IntegrityError):
        await adventurer_factory(run_id=run.id, mp=101)
