import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.parse import Login
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.features.waiting.login import (
    ALREADY_JOINED,
    INITIAL_PARTICIPATION_WINDOW,
    MAX_PARTICIPANTS,
    PARTY_FULL,
    handle_login,
)
from yt_live_dungeon.persistence.models import Egregore, RunAdventurer, RunEvent, RunState

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


def _context(session, run_id, viewer_id: str, *, received_at=NOW) -> CommandContext:
    return CommandContext(
        session=session,
        run_id=run_id,
        command_input=CommandInput(
            source="youtube_live",
            source_message_id=_unique("msg"),
            viewer_id=viewer_id,
            viewer_display_name="viewer",
            raw_text="@login",
            received_at=received_at,
        ),
        random_source=random.Random(1),
    )


async def _isolate_egregore_draw(db_session, egregore_id) -> None:
    await db_session.execute(
        update(Egregore).where(Egregore.id != egregore_id).values(is_active=False)
    )


async def _setup_egregore(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory
):
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    egregore = await egregore_factory(blessing_item_id=blessing_item.id)
    pool_item = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(egregore_id=egregore.id, item_id=pool_item.id)
    await _isolate_egregore_draw(db_session, egregore.id)
    return egregore, blessing_item, pool_item


async def test_login_succeeds_when_waiting(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory
):
    await _setup_egregore(
        db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory
    )
    run = await run_factory(state=RunState.WAITING)

    outcome = await handle_login(Login(), _context(db_session, run.id, "viewer-1"))

    assert outcome.processed is True
    adventurer = (
        await db_session.execute(
            select(RunAdventurer).where(
                RunAdventurer.run_id == run.id, RunAdventurer.youtube_id == "viewer-1"
            )
        )
    ).scalar_one()
    assert adventurer.is_participating is True
    assert adventurer.is_alive is True
    assert adventurer.waiting_ready_at is None


async def test_login_rejected_when_not_waiting(db_session, run_factory):
    run = await run_factory(state=RunState.BATTLE)

    outcome = await handle_login(Login(), _context(db_session, run.id, "viewer-1"))

    assert outcome.processed is False
    assert outcome.reason == "not_waiting"


async def test_login_rejected_when_already_joined(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory
):
    await _setup_egregore(
        db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory
    )
    run = await run_factory(state=RunState.WAITING)
    await handle_login(Login(), _context(db_session, run.id, "dup-viewer"))

    outcome = await handle_login(Login(), _context(db_session, run.id, "dup-viewer"))

    assert outcome.processed is False
    assert outcome.reason == ALREADY_JOINED

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(RunAdventurer)
            .where(RunAdventurer.run_id == run.id, RunAdventurer.youtube_id == "dup-viewer")
        )
    ).scalar_one()
    assert count == 1


async def test_login_succeeds_from_seven_participants(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory
):
    await _setup_egregore(
        db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory
    )
    run = await run_factory(state=RunState.WAITING)
    for i in range(7):
        outcome = await handle_login(Login(), _context(db_session, run.id, f"viewer-{i}"))
        assert outcome.processed is True

    outcome = await handle_login(Login(), _context(db_session, run.id, "eighth-viewer"))

    assert outcome.processed is True


async def test_login_rejected_when_eight_participants(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory
):
    await _setup_egregore(
        db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory
    )
    run = await run_factory(state=RunState.WAITING)
    for i in range(MAX_PARTICIPANTS):
        outcome = await handle_login(Login(), _context(db_session, run.id, f"viewer-{i}"))
        assert outcome.processed is True

    outcome = await handle_login(Login(), _context(db_session, run.id, "ninth-viewer"))

    assert outcome.processed is False
    assert outcome.reason == PARTY_FULL

    count = (
        await db_session.execute(
            select(func.count()).select_from(RunAdventurer).where(RunAdventurer.run_id == run.id)
        )
    ).scalar_one()
    assert count == MAX_PARTICIPANTS


async def test_first_successful_login_sets_the_deadline(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory
):
    await _setup_egregore(
        db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory
    )
    run = await run_factory(state=RunState.WAITING)
    assert run.waiting_deadline_at is None

    await handle_login(Login(), _context(db_session, run.id, "first-viewer", received_at=NOW))

    await db_session.refresh(run)
    assert run.waiting_deadline_at == NOW + INITIAL_PARTICIPATION_WINDOW


async def test_second_login_does_not_move_the_deadline(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory
):
    await _setup_egregore(
        db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory
    )
    run = await run_factory(state=RunState.WAITING)
    await handle_login(Login(), _context(db_session, run.id, "first-viewer", received_at=NOW))
    await db_session.refresh(run)
    first_deadline = run.waiting_deadline_at

    later = NOW + timedelta(minutes=2)
    await handle_login(Login(), _context(db_session, run.id, "second-viewer", received_at=later))

    await db_session.refresh(run)
    assert run.waiting_deadline_at == first_deadline


async def test_rejected_login_does_not_set_the_deadline(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory
):
    await _setup_egregore(
        db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory
    )
    run = await run_factory(state=RunState.WAITING)

    outcome = await handle_login(
        Login(), _context(db_session, run.id, "dup-viewer", received_at=NOW)
    )
    assert outcome.processed is True
    await handle_login(Login(), _context(db_session, run.id, "dup-viewer", received_at=NOW))

    later = NOW + timedelta(minutes=1)
    outcome = await handle_login(
        Login(), _context(db_session, run.id, "dup-viewer", received_at=later)
    )
    assert outcome.processed is False

    await db_session.refresh(run)
    assert run.waiting_deadline_at == NOW + INITIAL_PARTICIPATION_WINDOW


async def test_adventurer_login_event_body_for_new_adventurer(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory
):
    egregore, blessing_item, pool_item = await _setup_egregore(
        db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory
    )
    run = await run_factory(state=RunState.WAITING)

    await handle_login(Login(), _context(db_session, run.id, "new-viewer"))

    adventurer = (
        await db_session.execute(
            select(RunAdventurer).where(
                RunAdventurer.run_id == run.id, RunAdventurer.youtube_id == "new-viewer"
            )
        )
    ).scalar_one()
    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "adventurer_login"
            )
        )
    ).scalar_one()

    assert event.body == {
        "adventurer": str(adventurer.id),
        "egregore": egregore.id,
        "blessing_item": blessing_item.id,
        "pool_item": pool_item.id,
    }
