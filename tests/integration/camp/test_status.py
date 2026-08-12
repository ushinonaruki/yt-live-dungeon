import uuid
from datetime import UTC, datetime

from yt_live_dungeon.features.camp.status import handle_status
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.parse import Status
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.persistence.models import RunState

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
            raw_text="@status",
            received_at=NOW,
        ),
    )


async def test_status_returns_final_stats_including_items(
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
    spell = await spell_factory()
    blessing_item = await item_factory(
        granted_spell_id=spell.id,
        base_stat_modifiers={"max_hp": 50, "rr": 10},
        per_level_stat_modifiers={"max_hp": 5, "rr": 1},
    )
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    candidate_a = await item_factory(granted_spell_id=spell.id)
    candidate_b = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_a.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_b.id)

    run = await run_factory(state=RunState.CAMP, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id, spirit_id=spirit.id, hp=400, mp=80)
    camp = await camp_factory(
        run_id=run.id,
        spirit_id=spirit.id,
        candidate_a_item_id=candidate_a.id,
        candidate_b_item_id=candidate_b.id,
        floor=1,
    )
    await camp_member_factory(camp_id=camp.id, run_adventurer_id=adventurer.id)
    await inventory_item_factory(adventurer.id, blessing_item.id, slot=1, current_level=2)

    outcome = await handle_status(
        Status(), _context(db_session, run.id, adventurer.youtube_id)
    )

    assert outcome.processed is True
    result = outcome.result
    assert result["run_adventurer_id"] == str(adventurer.id)
    assert result["hp"] == 400
    assert result["max_hp"] == 500 + (50 + 5 * 2)
    assert result["mp"] == 80
    assert result["attributes"]["rr"] == 10 + 1 * 2
    assert result["spirit"] == {"id": spirit.id, "display_name": spirit.display_name}
    assert result["is_ready"] is False


async def test_status_reflects_is_ready(
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
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    candidate_a = await item_factory(granted_spell_id=spell.id)
    candidate_b = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_a.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_b.id)

    run = await run_factory(state=RunState.CAMP, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id, spirit_id=spirit.id)
    camp = await camp_factory(
        run_id=run.id,
        spirit_id=spirit.id,
        candidate_a_item_id=candidate_a.id,
        candidate_b_item_id=candidate_b.id,
        floor=1,
    )
    await camp_member_factory(camp_id=camp.id, run_adventurer_id=adventurer.id, ready_at=NOW)

    outcome = await handle_status(
        Status(), _context(db_session, run.id, adventurer.youtube_id)
    )

    assert outcome.result["is_ready"] is True


async def test_status_rejects_when_not_in_camp(
    db_session, run_factory, adventurer_factory
):
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id)

    outcome = await handle_status(
        Status(), _context(db_session, run.id, adventurer.youtube_id)
    )

    assert outcome.processed is False
    assert outcome.reason == "not_in_camp"


async def test_status_rejects_unjoined_viewer(
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

    outcome = await handle_status(
        Status(), _context(db_session, run.id, "someone_who_never_joined")
    )

    assert outcome.processed is False
    assert outcome.reason == "not_joined"
