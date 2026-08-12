import random
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from yt_live_dungeon.features.camp.spell_detail import handle_spell
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.parse import Spell as SpellCommand
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.persistence.models import RunEvent, RunState

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


def _context(session, run_id, viewer_id: str, command: str) -> CommandContext:
    return CommandContext(
        session=session,
        run_id=run_id,
        command_input=CommandInput(
            source="youtube_live",
            source_message_id=_unique("msg"),
            viewer_id=viewer_id,
            viewer_display_name="viewer",
            raw_text=f"@{command}",
            received_at=NOW,
        ),
        random_source=random.Random(),
    )


async def _setup(
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
):
    spell = await spell_factory(command="firebolt")
    blessing_item = await item_factory(granted_spell_id=spell.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    candidate_a = await item_factory(granted_spell_id=spell.id)
    candidate_b = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_a.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_b.id)

    run = await run_factory(state=RunState.CAMP, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id, hp=500, mp=100)
    camp = await camp_factory(
        run_id=run.id,
        spirit_id=spirit.id,
        candidate_a_item_id=candidate_a.id,
        candidate_b_item_id=candidate_b.id,
        floor=1,
    )
    await camp_member_factory(camp_id=camp.id, run_adventurer_id=adventurer.id)

    return spell, blessing_item, run, adventurer


async def test_returns_details_for_unlocked_spell(
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
    spell, blessing_item, run, adventurer = await _setup(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )
    await inventory_item_factory(adventurer.id, blessing_item.id, slot=1, current_level=1)

    outcome = await handle_spell(
        SpellCommand(command="firebolt", raw_argument=""),
        _context(db_session, run.id, adventurer.youtube_id, "firebolt"),
    )

    assert outcome.processed is True
    assert outcome.result == {
        "id": spell.id,
        "command": "firebolt",
        "display_name": spell.display_name,
        "attribute": spell.attribute,
        "mp_cost": spell.mp_cost,
        "target_rule": spell.target_rule,
        "effects": spell.effects,
    }


async def test_deduplicates_spell_shared_by_multiple_items(
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
    spell, blessing_item, run, adventurer = await _setup(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )
    second_item = await item_factory(granted_spell_id=spell.id)
    await inventory_item_factory(adventurer.id, blessing_item.id, slot=1, current_level=1)
    await inventory_item_factory(adventurer.id, second_item.id, slot=2, current_level=1)

    outcome = await handle_spell(
        SpellCommand(command="firebolt", raw_argument=""),
        _context(db_session, run.id, adventurer.youtube_id, "firebolt"),
    )

    assert outcome.processed is True
    assert outcome.result["id"] == spell.id


async def test_spell_rejected_when_not_in_camp(db_session, run_factory, adventurer_factory):
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id)

    outcome = await handle_spell(
        SpellCommand(command="firebolt", raw_argument=""),
        _context(db_session, run.id, adventurer.youtube_id, "firebolt"),
    )

    assert outcome.processed is False
    assert outcome.reason == "not_in_camp"


async def test_spell_rejected_when_viewer_not_joined(
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
    spell, _blessing_item, run, _adventurer = await _setup(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )

    outcome = await handle_spell(
        SpellCommand(command="firebolt", raw_argument=""),
        _context(db_session, run.id, "someone_who_never_joined", "firebolt"),
    )

    assert outcome.processed is False
    assert outcome.reason == "not_joined"


async def test_unknown_spell_command(
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
    _spell, _blessing_item, run, adventurer = await _setup(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )

    outcome = await handle_spell(
        SpellCommand(command="does_not_exist", raw_argument=""),
        _context(db_session, run.id, adventurer.youtube_id, "does_not_exist"),
    )

    assert outcome.processed is False
    assert outcome.reason == "unknown_spell"


async def test_spell_not_unlocked(
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
    _spell, _blessing_item, run, adventurer = await _setup(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )
    # adventurer never acquired any item, so "firebolt" is not unlocked

    outcome = await handle_spell(
        SpellCommand(command="firebolt", raw_argument=""),
        _context(db_session, run.id, adventurer.youtube_id, "firebolt"),
    )

    assert outcome.processed is False
    assert outcome.reason == "spell_not_unlocked"


async def test_spell_detail_does_not_mutate_mp_or_state(
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
    spell, blessing_item, run, adventurer = await _setup(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )
    await inventory_item_factory(adventurer.id, blessing_item.id, slot=1, current_level=1)

    await handle_spell(
        SpellCommand(command="firebolt", raw_argument=""),
        _context(db_session, run.id, adventurer.youtube_id, "firebolt"),
    )

    assert adventurer.mp == 100
    assert adventurer.hp == 500

    event_count = (
        await db_session.execute(
            select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run.id)
        )
    ).scalar_one()
    assert event_count == 0
