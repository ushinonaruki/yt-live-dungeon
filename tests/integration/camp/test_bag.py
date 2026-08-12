import uuid
from datetime import UTC, datetime

from yt_live_dungeon.features.camp.bag import handle_bag
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.parse import Bag
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
            raw_text="@bag",
            received_at=NOW,
        ),
    )


async def test_bag_rejected_when_not_in_camp(db_session, run_factory, adventurer_factory):
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id)

    outcome = await handle_bag(Bag(), _context(db_session, run.id, adventurer.youtube_id))

    assert outcome.processed is False
    assert outcome.reason == "not_in_camp"


async def test_bag_rejected_when_viewer_not_joined(
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

    outcome = await handle_bag(
        Bag(), _context(db_session, run.id, "someone_who_never_joined")
    )

    assert outcome.processed is False
    assert outcome.reason == "not_joined"


async def test_bag_returns_slot_ordered_items_with_final_modifiers_and_spell(
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
    spell_a = await spell_factory(command="spell_a")
    spell_b = await spell_factory(command="spell_b")
    blessing_item = await item_factory(granted_spell_id=spell_a.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    candidate_a = await item_factory(granted_spell_id=spell_a.id)
    candidate_b = await item_factory(granted_spell_id=spell_a.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_a.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_b.id)

    second_item = await item_factory(
        granted_spell_id=spell_b.id,
        attribute="BB",
        base_stat_modifiers={"bb": 3},
        per_level_stat_modifiers={"bb": 2},
    )

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

    # inserted out of slot order to prove the handler sorts by slot
    await inventory_item_factory(adventurer.id, second_item.id, slot=2, current_level=3)
    await inventory_item_factory(adventurer.id, blessing_item.id, slot=1, current_level=1)

    outcome = await handle_bag(Bag(), _context(db_session, run.id, adventurer.youtube_id))

    assert outcome.processed is True
    items = outcome.result["items"]
    assert [entry["slot"] for entry in items] == [1, 2]

    first, second = items
    assert first["item_id"] == blessing_item.id
    assert first["current_level"] == 1
    assert first["spell"]["command"] == "spell_a"

    assert second["item_id"] == second_item.id
    assert second["current_level"] == 3
    assert second["final_modifiers"]["bb"] == 3 + 2 * 3
    assert second["spell"]["command"] == "spell_b"
    assert isinstance(second["final_modifiers"], dict)
