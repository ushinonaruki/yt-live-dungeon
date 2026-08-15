import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.parse import Logout
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.features.waiting.logout import handle_logout
from yt_live_dungeon.persistence.models import (
    EnemyGroup,
    RunAdventurer,
    RunEnemy,
    RunEvent,
    RunState,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


def _context(session, run_id, viewer_id: str, *, raw_text="@logout") -> CommandContext:
    return CommandContext(
        session=session,
        run_id=run_id,
        command_input=CommandInput(
            source="youtube_live",
            source_message_id=_unique("msg"),
            viewer_id=viewer_id,
            viewer_display_name="viewer",
            raw_text=raw_text,
            received_at=NOW,
        ),
        random_source=random.Random(1),
    )


async def test_logout_succeeds_and_stops_participation(
    db_session, run_factory, adventurer_factory
):
    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=NOW + timedelta(minutes=5))
    await adventurer_factory(run_id=run.id, youtube_id="viewer-1")
    await adventurer_factory(run_id=run.id, youtube_id="viewer-2")

    outcome = await handle_logout(Logout(), _context(db_session, run.id, "viewer-1"))

    assert outcome.processed is True
    adventurer = (
        await db_session.execute(
            select(RunAdventurer).where(
                RunAdventurer.run_id == run.id, RunAdventurer.youtube_id == "viewer-1"
            )
        )
    ).scalar_one()
    assert adventurer.is_participating is False

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "adventurer_logout"
            )
        )
    ).scalar_one()
    assert event.body == {"adventurer": str(adventurer.id)}


async def test_logout_rejected_when_not_joined(db_session, run_factory):
    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=NOW + timedelta(minutes=5))

    outcome = await handle_logout(Logout(), _context(db_session, run.id, "never-joined"))

    assert outcome.processed is False
    assert outcome.reason == "not_joined"


async def test_logout_to_zero_participants_ends_run_as_game_over(
    db_session, run_factory, adventurer_factory
):
    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=NOW + timedelta(minutes=5))
    await adventurer_factory(run_id=run.id, youtube_id="only-viewer")

    outcome = await handle_logout(Logout(), _context(db_session, run.id, "only-viewer"))

    assert outcome.processed is True
    await db_session.refresh(run)
    assert run.state == RunState.GAME_OVER
    assert run.ended_at == NOW

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "run_game_over"
            )
        )
    ).scalar_one()
    assert event.body == {"floor": 1, "reason": "no_participants"}


async def test_logout_leaving_only_ready_participants_starts_floor_1(
    db_session,
    run_factory,
    adventurer_factory,
    enemy_factory,
    enemy_group_factory,
):
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    await db_session.execute(
        update(EnemyGroup).where(EnemyGroup.id != group.id).values(is_active=False)
    )

    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=NOW + timedelta(minutes=5))
    ready_adventurer = await adventurer_factory(
        run_id=run.id, youtube_id="ready-viewer", waiting_ready_at=NOW
    )
    not_ready_adventurer = await adventurer_factory(
        run_id=run.id, youtube_id="leaving-viewer", waiting_ready_at=None
    )

    outcome = await handle_logout(Logout(), _context(db_session, run.id, "leaving-viewer"))

    assert outcome.processed is True
    await db_session.refresh(run)
    assert run.state == RunState.BATTLE
    assert run.current_floor == 1

    spawned = (
        await db_session.execute(
            select(RunEnemy).where(RunEnemy.run_id == run.id, RunEnemy.floor == 1)
        )
    ).scalars().all()
    assert len(spawned) == 1
    assert spawned[0].mp_regen_rate == 1  # only ready_adventurer still participates

    await db_session.refresh(not_ready_adventurer)
    assert not_ready_adventurer.is_participating is False
    await db_session.refresh(ready_adventurer)
    assert ready_adventurer.is_participating is True
