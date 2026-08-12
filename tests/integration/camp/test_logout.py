import random
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from yt_live_dungeon.features.camp.logout import handle_logout
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.parse import Logout
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.persistence.models import RunAdventurerItem, RunEvent, RunState
from yt_live_dungeon.persistence.queries.adventurer import list_active_participants
from yt_live_dungeon.persistence.queries.camp import get_camp_member

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
            raw_text="@logout",
            received_at=NOW,
        ),
        random_source=random.Random(1),
    )


async def _setup_camp_with_members(
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    *,
    member_count: int = 2,
    ready_flags: list[bool] | None = None,
):
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    candidate_a = await item_factory(granted_spell_id=spell.id)
    candidate_b = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_a.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_b.id)

    run = await run_factory(state=RunState.CAMP, current_floor=1)
    camp = await camp_factory(
        run_id=run.id,
        spirit_id=spirit.id,
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


async def test_logout_sets_is_participating_false_and_left_at(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
):
    run, camp, [adventurer, _other] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )

    outcome = await handle_logout(
        Logout(), _context(db_session, run.id, adventurer.youtube_id)
    )

    assert outcome.processed is True
    assert adventurer.is_participating is False

    member = await get_camp_member(db_session, camp.id, adventurer.id)
    assert member.left_at == NOW


async def test_logout_preserves_adventurer_spirit_items_hp_mp(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    inventory_item_factory,
):
    run, camp, [adventurer, _other] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )
    item = await item_factory(granted_spell_id=(await spell_factory()).id)
    await inventory_item_factory(adventurer.id, item.id, slot=3, current_level=4)
    adventurer.hp = 250
    adventurer.mp = 60
    await db_session.flush()

    await handle_logout(Logout(), _context(db_session, run.id, adventurer.youtube_id))

    assert adventurer.hp == 250
    assert adventurer.mp == 60

    rows = (
        await db_session.execute(
            select(RunAdventurerItem).where(
                RunAdventurerItem.run_adventurer_id == adventurer.id
            )
        )
    ).scalars().all()
    assert any(row.item_id == item.id and row.current_level == 4 for row in rows)


async def test_logout_frees_a_participant_slot(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
):
    run, _camp, [adventurer, other] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )

    await handle_logout(Logout(), _context(db_session, run.id, adventurer.youtube_id))

    remaining = await list_active_participants(db_session, run.id)
    assert [a.id for a in remaining] == [other.id]


async def test_logout_that_leaves_all_remaining_ready_ends_camp(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
):
    run, _camp, [not_ready, ready] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        member_count=2,
        ready_flags=[False, True],
    )

    outcome = await handle_logout(
        Logout(), _context(db_session, run.id, not_ready.youtube_id)
    )

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
    assert event.body["participant_count"] == 1


async def test_logout_of_last_participant_retires_the_run(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
):
    run, _camp, [only_adventurer] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        member_count=1,
    )

    await handle_logout(Logout(), _context(db_session, run.id, only_adventurer.youtube_id))

    await db_session.refresh(run)
    assert run.state == RunState.RETIRE
    assert run.ended_at == NOW

    event = (
        await db_session.execute(
            select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.event_type == "camp_ended")
        )
    ).scalar_one()
    assert event.body["reason"] == "empty"
    assert event.body["participant_count"] == 0

    retired_event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "run_retired"
            )
        )
    ).scalar_one()
    assert retired_event.body == {"floor": 1}


async def test_logout_does_not_end_camp_when_other_participants_remain_unready(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
):
    run, _camp, [leaving, still_here] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        member_count=2,
        ready_flags=[False, False],
    )

    await handle_logout(Logout(), _context(db_session, run.id, leaving.youtube_id))

    await db_session.refresh(run)
    assert run.state == RunState.CAMP


async def test_logout_rejected_when_not_in_camp(db_session, run_factory, adventurer_factory):
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id)

    outcome = await handle_logout(
        Logout(), _context(db_session, run.id, adventurer.youtube_id)
    )

    assert outcome.processed is False
    assert outcome.reason == "not_in_camp"


async def test_logout_rejected_when_not_joined(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
):
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    candidate_a = await item_factory(granted_spell_id=spell.id)
    candidate_b = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_a.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_b.id)
    run = await run_factory(state=RunState.CAMP, current_floor=1)
    await camp_factory(
        run_id=run.id,
        spirit_id=spirit.id,
        candidate_a_item_id=candidate_a.id,
        candidate_b_item_id=candidate_b.id,
        floor=1,
    )

    outcome = await handle_logout(
        Logout(), _context(db_session, run.id, "someone_who_never_joined")
    )

    assert outcome.processed is False
    assert outcome.reason == "not_joined"


async def test_adventurer_logout_event_body(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
):
    run, _camp, [adventurer, _other] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )

    await handle_logout(Logout(), _context(db_session, run.id, adventurer.youtube_id))

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "adventurer_logout"
            )
        )
    ).scalar_one()
    assert event.body == {"adventurer": str(adventurer.id)}
