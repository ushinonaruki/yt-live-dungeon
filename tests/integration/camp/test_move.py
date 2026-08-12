import random
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import select

from yt_live_dungeon.features.camp.move import handle_move
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.parse import Move
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.persistence.models import RunAdventurerItem, RunEvent, RunState

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


async def _setup_camp_with_items(
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    inventory_item_factory,
    *,
    item_count: int,
) -> SimpleNamespace:
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    candidate_a = await item_factory(granted_spell_id=spell.id)
    candidate_b = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_a.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_b.id)

    run = await run_factory(state=RunState.CAMP, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id)
    camp = await camp_factory(
        run_id=run.id,
        spirit_id=spirit.id,
        candidate_a_item_id=candidate_a.id,
        candidate_b_item_id=candidate_b.id,
        floor=1,
    )
    await camp_member_factory(camp_id=camp.id, run_adventurer_id=adventurer.id)

    owned_items = []
    for slot in range(1, item_count + 1):
        item = await item_factory(granted_spell_id=spell.id)
        row = await inventory_item_factory(adventurer.id, item.id, slot=slot)
        owned_items.append(row)

    return SimpleNamespace(run=run, adventurer=adventurer, camp=camp, rows=owned_items)


def _move_context(session, run_id, viewer_id: str, order: str) -> CommandContext:
    return CommandContext(
        session=session,
        run_id=run_id,
        command_input=CommandInput(
            source="youtube_live",
            source_message_id=_unique("msg"),
            viewer_id=viewer_id,
            viewer_display_name="viewer",
            raw_text=f"@move {order}",
            received_at=NOW,
        ),
        random_source=random.Random(),
    )


async def _rows_by_item_id(session, run_adventurer_id):
    result = await session.execute(
        select(RunAdventurerItem).where(RunAdventurerItem.run_adventurer_id == run_adventurer_id)
    )
    return {row.item_id: row for row in result.scalars().all()}


async def test_move_rejected_when_not_in_camp(db_session, run_factory, adventurer_factory):
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id)

    outcome = await handle_move(
        Move(order="1"),
        _move_context(db_session, run.id, adventurer.youtube_id, "1"),
    )

    assert outcome.processed is False
    assert outcome.reason == "not_in_camp"


async def test_move_rejected_when_viewer_not_joined(
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

    outcome = await handle_move(
        Move(order="1"),
        _move_context(db_session, run.id, "someone_who_never_joined", "1"),
    )

    assert outcome.processed is False
    assert outcome.reason == "not_joined"


async def test_move_reorders_slots_as_requested(
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
    scenario = await _setup_camp_with_items(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        inventory_item_factory,
        item_count=5,
    )
    old_item_ids = [row.item_id for row in scenario.rows]  # index0=old slot1, etc.

    outcome = await handle_move(
        Move(order="31425"),
        _move_context(db_session, scenario.run.id, scenario.adventurer.youtube_id, "31425"),
    )

    assert outcome.processed is True

    rows = await _rows_by_item_id(db_session, scenario.adventurer.id)
    # old3,old1,old4,old2,old5 -> new slots 1,2,3,4,5
    assert rows[old_item_ids[2]].slot == 1
    assert rows[old_item_ids[0]].slot == 2
    assert rows[old_item_ids[3]].slot == 3
    assert rows[old_item_ids[1]].slot == 4
    assert rows[old_item_ids[4]].slot == 5


async def test_move_swaps_two_slots_without_unique_constraint_violation(
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
    scenario = await _setup_camp_with_items(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        inventory_item_factory,
        item_count=2,
    )
    old_item_ids = [row.item_id for row in scenario.rows]

    # A naive in-place UPDATE swap (1->2, 2->1) would hit the
    # (adventurer, slot) unique constraint mid-transaction.
    outcome = await handle_move(
        Move(order="21"),
        _move_context(db_session, scenario.run.id, scenario.adventurer.youtube_id, "21"),
    )

    assert outcome.processed is True
    rows = await _rows_by_item_id(db_session, scenario.adventurer.id)
    assert rows[old_item_ids[1]].slot == 1
    assert rows[old_item_ids[0]].slot == 2


async def test_move_rejects_duplicate_slot_and_leaves_entries_unchanged(
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
    scenario = await _setup_camp_with_items(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        inventory_item_factory,
        item_count=3,
    )
    original = {row.item_id: row.slot for row in scenario.rows}

    outcome = await handle_move(
        Move(order="121"),
        _move_context(db_session, scenario.run.id, scenario.adventurer.youtube_id, "121"),
    )

    assert outcome.processed is False
    assert outcome.reason == "invalid_syntax"
    rows = await _rows_by_item_id(db_session, scenario.adventurer.id)
    assert {item_id: row.slot for item_id, row in rows.items()} == original


async def test_move_rejects_missing_slot_and_leaves_entries_unchanged(
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
    scenario = await _setup_camp_with_items(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        inventory_item_factory,
        item_count=3,
    )
    original = {row.item_id: row.slot for row in scenario.rows}

    outcome = await handle_move(
        Move(order="12"),
        _move_context(db_session, scenario.run.id, scenario.adventurer.youtube_id, "12"),
    )

    assert outcome.processed is False
    assert outcome.reason == "invalid_syntax"
    rows = await _rows_by_item_id(db_session, scenario.adventurer.id)
    assert {item_id: row.slot for item_id, row in rows.items()} == original


async def test_move_rejects_unknown_slot_and_leaves_entries_unchanged(
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
    scenario = await _setup_camp_with_items(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        inventory_item_factory,
        item_count=3,
    )
    original = {row.item_id: row.slot for row in scenario.rows}

    outcome = await handle_move(
        Move(order="129"),
        _move_context(db_session, scenario.run.id, scenario.adventurer.youtube_id, "129"),
    )

    assert outcome.processed is False
    assert outcome.reason == "invalid_syntax"
    rows = await _rows_by_item_id(db_session, scenario.adventurer.id)
    assert {item_id: row.slot for item_id, row in rows.items()} == original


async def test_move_rejects_length_mismatch_and_leaves_entries_unchanged(
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
    scenario = await _setup_camp_with_items(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        inventory_item_factory,
        item_count=3,
    )
    original = {row.item_id: row.slot for row in scenario.rows}

    outcome = await handle_move(
        Move(order="1234"),
        _move_context(db_session, scenario.run.id, scenario.adventurer.youtube_id, "1234"),
    )

    assert outcome.processed is False
    assert outcome.reason == "invalid_syntax"
    rows = await _rows_by_item_id(db_session, scenario.adventurer.id)
    assert {item_id: row.slot for item_id, row in rows.items()} == original


async def test_move_records_inventory_moved_event(
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
    scenario = await _setup_camp_with_items(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        inventory_item_factory,
        item_count=3,
    )

    await handle_move(
        Move(order="321"),
        _move_context(db_session, scenario.run.id, scenario.adventurer.youtube_id, "321"),
    )

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == scenario.run.id, RunEvent.event_type == "inventory_moved"
            )
        )
    ).scalar_one()
    assert event.body["old_order"] == "123"
    assert event.body["new_order"] == "321"
    assert event.body["adventurer"] == str(scenario.adventurer.id)
