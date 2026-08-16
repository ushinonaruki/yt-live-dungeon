from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from yt_live_dungeon.persistence.models import RunCamp


def camp_window() -> tuple[datetime, datetime]:
    started_at = datetime.now(UTC)
    deadline_at = started_at + timedelta(minutes=5)
    return started_at, deadline_at


async def _setup(spell_factory, item_factory, egregore_factory, run_factory):
    spell = await spell_factory()
    item_a = await item_factory(granted_spell_id=spell.id, item_key="item_a")
    item_b = await item_factory(granted_spell_id=spell.id, item_key="item_b")
    egregore = await egregore_factory(blessing_item_id=item_a.id)
    run = await run_factory()
    return run, egregore, item_a, item_b


async def test_rejects_equal_candidates(
    db_session, spell_factory, item_factory, egregore_factory, run_factory
):
    run, egregore, item_a, _ = await _setup(
        spell_factory, item_factory, egregore_factory, run_factory
    )
    started_at, deadline_at = camp_window()

    with pytest.raises(IntegrityError):
        db_session.add(
            RunCamp(
                run_id=run.id,
                floor=1,
                egregore_id=egregore.id,
                candidate_a_item_id=item_a.id,
                candidate_b_item_id=item_a.id,
                started_at=started_at,
                deadline_at=deadline_at,
            )
        )
        await db_session.flush()


async def test_rejects_second_camp_for_same_run_and_floor(
    db_session, spell_factory, item_factory, egregore_factory, run_factory
):
    run, egregore, item_a, item_b = await _setup(
        spell_factory, item_factory, egregore_factory, run_factory
    )
    started_at, deadline_at = camp_window()

    db_session.add(
        RunCamp(
            run_id=run.id,
            floor=1,
            egregore_id=egregore.id,
            candidate_a_item_id=item_a.id,
            candidate_b_item_id=item_b.id,
            started_at=started_at,
            deadline_at=deadline_at,
        )
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        db_session.add(
            RunCamp(
                run_id=run.id,
                floor=1,
                egregore_id=egregore.id,
                candidate_a_item_id=item_a.id,
                candidate_b_item_id=item_b.id,
                started_at=started_at,
                deadline_at=deadline_at,
            )
        )
        await db_session.flush()
