import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.parse import Ready
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.features.waiting.ready import ALREADY_READY, handle_ready
from yt_live_dungeon.persistence.models import EnemyGroup, RunEnemy, RunEvent, RunState

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
            raw_text="@ready",
            received_at=received_at,
        ),
        random_source=random.Random(1),
    )


async def test_ready_rejected_when_not_joined(db_session, run_factory):
    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=NOW + timedelta(minutes=5))

    outcome = await handle_ready(Ready(), _context(db_session, run.id, "never-joined"))

    assert outcome.processed is False
    assert outcome.reason == "not_joined"


async def test_ready_succeeds_when_others_remain_unready(
    db_session, run_factory, adventurer_factory
):
    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=NOW + timedelta(minutes=5))
    await adventurer_factory(run_id=run.id, youtube_id="viewer-1")
    await adventurer_factory(run_id=run.id, youtube_id="viewer-2")

    outcome = await handle_ready(Ready(), _context(db_session, run.id, "viewer-1"))

    assert outcome.processed is True
    await db_session.refresh(run)
    assert run.state == RunState.WAITING

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "adventurer_ready"
            )
        )
    ).scalar_one()
    assert event.body["reason"] == "manual"


async def test_ready_rejected_when_already_ready(db_session, run_factory, adventurer_factory):
    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=NOW + timedelta(minutes=5))
    await adventurer_factory(run_id=run.id, youtube_id="viewer-1", waiting_ready_at=NOW)
    await adventurer_factory(run_id=run.id, youtube_id="viewer-2")

    outcome = await handle_ready(Ready(), _context(db_session, run.id, "viewer-1"))

    assert outcome.processed is False
    assert outcome.reason == ALREADY_READY


async def test_ready_of_sole_participant_starts_floor_1(
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
    await adventurer_factory(run_id=run.id, youtube_id="only-viewer")

    outcome = await handle_ready(Ready(), _context(db_session, run.id, "only-viewer"))

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
    assert spawned[0].role == "master"
    assert spawned[0].group_id == group.id
    assert spawned[0].mp_regen_rate == 1

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "floor_started"
            )
        )
    ).scalar_one()
    assert event.body == {"floor": 1}


async def test_ready_does_not_start_floor_while_someone_remains_unready(
    db_session, run_factory, adventurer_factory
):
    run = await run_factory(state=RunState.WAITING, waiting_deadline_at=NOW + timedelta(minutes=5))
    await adventurer_factory(run_id=run.id, youtube_id="viewer-1")
    await adventurer_factory(run_id=run.id, youtube_id="viewer-2")

    await handle_ready(Ready(), _context(db_session, run.id, "viewer-1"))

    await db_session.refresh(run)
    assert run.state == RunState.WAITING
