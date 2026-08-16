import random
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from yt_live_dungeon.features.camp.ready import ALREADY_READY, handle_ready
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.parse import Ready
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.persistence.models import RunEvent, RunState

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


def _context(session, run_id, viewer_id: str) -> CommandContext:
    return CommandContext(
        session=session,
        run_id=run_id,
        command_input=CommandInput(
            source="youtube_live",
            source_message_id=_unique("msg"),
            viewer_id=viewer_id,
            viewer_display_name="viewer",
            raw_text="@ready",
            received_at=NOW,
        ),
        random_source=random.Random(1),
    )


async def _setup_camp_with_members(
    spell_factory,
    item_factory,
    egregore_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    enemy_factory,
    enemy_group_factory,
    *,
    member_count: int = 2,
    ready_flags: list[bool] | None = None,
):
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    egregore = await egregore_factory(blessing_item_id=blessing_item.id)
    candidate_a = await item_factory(granted_spell_id=spell.id)
    candidate_b = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(egregore_id=egregore.id, item_id=candidate_a.id)
    await pool_entry_factory(egregore_id=egregore.id, item_id=candidate_b.id)

    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )

    run = await run_factory(state=RunState.CAMP, current_floor=1, next_group_id=group.id)
    camp = await camp_factory(
        run_id=run.id,
        egregore_id=egregore.id,
        candidate_a_item_id=candidate_a.id,
        candidate_b_item_id=candidate_b.id,
        floor=1,
    )

    ready_flags = ready_flags or [False] * member_count
    adventurers = []
    for i in range(member_count):
        adventurer = await adventurer_factory(run_id=run.id)
        await camp_member_factory(
            camp_id=camp.id,
            run_adventurer_id=adventurer.id,
            ready_at=NOW if ready_flags[i] else None,
        )
        adventurers.append(adventurer)

    return run, camp, adventurers


async def test_ready_succeeds_without_selecting_an_action(
    db_session,
    spell_factory,
    item_factory,
    egregore_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    enemy_factory,
    enemy_group_factory,
):
    run, camp, [a, b] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        egregore_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        enemy_factory,
        enemy_group_factory,
    )

    outcome = await handle_ready(Ready(), _context(db_session, run.id, a.youtube_id))

    assert outcome.processed is True


async def test_ready_all_participants_ready_ends_camp_immediately(
    db_session,
    spell_factory,
    item_factory,
    egregore_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    enemy_factory,
    enemy_group_factory,
):
    run, camp, [a, b] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        egregore_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        enemy_factory,
        enemy_group_factory,
        ready_flags=[False, True],
    )

    outcome = await handle_ready(Ready(), _context(db_session, run.id, a.youtube_id))

    assert outcome.processed is True
    await db_session.refresh(run)
    assert run.state == RunState.BATTLE
    assert run.current_floor == 2

    event = (
        await db_session.execute(
            select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.event_type == "camp_ended")
        )
    ).scalar_one()
    assert event.body["reason"] == "all_ready"
    assert event.body["participant_count"] == 2


async def test_ready_does_not_end_camp_while_others_are_unready(
    db_session,
    spell_factory,
    item_factory,
    egregore_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    enemy_factory,
    enemy_group_factory,
):
    run, camp, [a, b] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        egregore_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        enemy_factory,
        enemy_group_factory,
        ready_flags=[False, False],
    )

    await handle_ready(Ready(), _context(db_session, run.id, a.youtube_id))

    await db_session.refresh(run)
    assert run.state == RunState.CAMP


async def test_second_ready_call_is_rejected_without_mutation(
    db_session,
    spell_factory,
    item_factory,
    egregore_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    enemy_factory,
    enemy_group_factory,
):
    run, camp, [a, b] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        egregore_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        enemy_factory,
        enemy_group_factory,
        ready_flags=[False, False],
    )

    first = await handle_ready(Ready(), _context(db_session, run.id, a.youtube_id))
    second = await handle_ready(Ready(), _context(db_session, run.id, a.youtube_id))

    assert first.processed is True
    assert second.processed is False
    assert second.reason == ALREADY_READY

    events = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "adventurer_ready"
            )
        )
    ).scalars().all()
    assert len(events) == 1


async def test_ready_rejected_when_not_in_camp(db_session, run_factory, adventurer_factory):
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id)

    outcome = await handle_ready(Ready(), _context(db_session, run.id, adventurer.youtube_id))

    assert outcome.processed is False
    assert outcome.reason == "not_in_camp"


async def test_ready_rejected_when_not_joined(
    db_session,
    spell_factory,
    item_factory,
    egregore_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
):
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    egregore = await egregore_factory(blessing_item_id=blessing_item.id)
    candidate_a = await item_factory(granted_spell_id=spell.id)
    candidate_b = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(egregore_id=egregore.id, item_id=candidate_a.id)
    await pool_entry_factory(egregore_id=egregore.id, item_id=candidate_b.id)
    run = await run_factory(state=RunState.CAMP, current_floor=1)
    await camp_factory(
        run_id=run.id,
        egregore_id=egregore.id,
        candidate_a_item_id=candidate_a.id,
        candidate_b_item_id=candidate_b.id,
        floor=1,
    )

    outcome = await handle_ready(
        Ready(), _context(db_session, run.id, "someone_who_never_joined")
    )

    assert outcome.processed is False
    assert outcome.reason == "not_joined"


async def test_adventurer_ready_event_body_has_manual_reason(
    db_session,
    spell_factory,
    item_factory,
    egregore_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    enemy_factory,
    enemy_group_factory,
):
    run, camp, [a, b] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        egregore_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        enemy_factory,
        enemy_group_factory,
    )

    await handle_ready(Ready(), _context(db_session, run.id, a.youtube_id))

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "adventurer_ready"
            )
        )
    ).scalar_one()
    assert event.body == {"adventurer": str(a.id), "reason": "manual"}
