import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import func, select

from yt_live_dungeon.domain.inventory import MAX_SLOTS
from yt_live_dungeon.features.camp.handlers import build_camp_handlers
from yt_live_dungeon.features.camp.select_action import (
    ACTION_ALREADY_SELECTED,
    ACTION_NOT_AVAILABLE,
    handle_select,
)
from yt_live_dungeon.features.camp.start import start_camp
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.parse import Select
from yt_live_dungeon.features.commands.submit import submit_command
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Item,
    ProcessedCommand,
    Run,
    RunAdventurer,
    RunAdventurerItem,
    RunCamp,
    RunCampMember,
    RunEvent,
    RunState,
    Spell,
    Spirit,
    SpiritItemPoolEntry,
)
from yt_live_dungeon.persistence.queries.camp import get_camp_member

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


async def _setup_camp(
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    *,
    can_select_action: bool = True,
    selected_action: str | None = None,
    representative_attribute: str = "RR",
) -> SimpleNamespace:
    spell = await spell_factory()
    blessing_item = await item_factory(
        granted_spell_id=spell.id, attribute=representative_attribute
    )
    spirit = await spirit_factory(
        blessing_item_id=blessing_item.id, representative_attribute=representative_attribute
    )

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
    member = await camp_member_factory(
        camp_id=camp.id,
        run_adventurer_id=adventurer.id,
        can_select_action=can_select_action,
        selected_action=selected_action,
    )

    return SimpleNamespace(
        spell=spell,
        blessing_item=blessing_item,
        spirit=spirit,
        candidate_a=candidate_a,
        candidate_b=candidate_b,
        run=run,
        adventurer=adventurer,
        camp=camp,
        member=member,
    )


def _context(session, run_id, viewer_id: str, raw_text: str) -> CommandContext:
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
        random_source=random.Random(),
    )


async def _select(session, scenario: SimpleNamespace, value: int):
    return await handle_select(
        Select(value=value),
        _context(session, scenario.run.id, scenario.adventurer.youtube_id, f"@select {value}"),
    )


async def test_rest_heals_100_hp(
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
    scenario = await _setup_camp(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )
    scenario.adventurer.hp = 300

    outcome = await _select(db_session, scenario, 1)

    assert outcome.processed is True
    assert outcome.reason is None
    assert scenario.adventurer.hp == 400
    assert scenario.member.selected_action == "rest"

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == scenario.run.id, RunEvent.event_type == "camp_action_selected"
            )
        )
    ).scalar_one()
    assert event.body == {"adventurer": str(scenario.adventurer.id), "action": "rest"}


async def test_rest_does_not_exceed_max_hp(
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
    scenario = await _setup_camp(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )
    scenario.adventurer.hp = 480  # base_max_hp defaults to 500, no items yet

    await _select(db_session, scenario, 1)

    assert scenario.adventurer.hp == 500


async def test_new_candidate_acquisition_is_level_1(
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
    scenario = await _setup_camp(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )

    outcome = await _select(db_session, scenario, 2)

    assert outcome.processed is True
    assert scenario.member.selected_action == "candidate_a"

    row = (
        await db_session.execute(
            select(RunAdventurerItem).where(
                RunAdventurerItem.run_adventurer_id == scenario.adventurer.id,
                RunAdventurerItem.item_id == scenario.candidate_a.id,
            )
        )
    ).scalar_one()
    assert row.current_level == 1


async def test_duplicate_candidate_acquisition_increases_level_by_5_without_new_slot(
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
    scenario = await _setup_camp(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )
    await inventory_item_factory(
        scenario.adventurer.id, scenario.candidate_a.id, slot=1, current_level=3
    )

    outcome = await _select(db_session, scenario, 2)

    assert outcome.processed is True

    rows = (
        (
            await db_session.execute(
                select(RunAdventurerItem).where(
                    RunAdventurerItem.run_adventurer_id == scenario.adventurer.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].current_level == 8
    assert rows[0].slot == 1


async def test_unowned_candidate_fails_when_inventory_full(
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
    scenario = await _setup_camp(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )
    for slot in range(1, MAX_SLOTS + 1):
        filler = await item_factory(granted_spell_id=scenario.spell.id)
        await inventory_item_factory(scenario.adventurer.id, filler.id, slot=slot)

    outcome = await _select(db_session, scenario, 2)

    assert outcome.processed is False
    assert outcome.reason == "inventory_full"
    assert scenario.member.selected_action is None
    assert scenario.member.selected_at is None

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(RunAdventurerItem)
            .where(RunAdventurerItem.run_adventurer_id == scenario.adventurer.id)
        )
    ).scalar_one()
    assert count == MAX_SLOTS

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == scenario.run.id, RunEvent.event_type == "camp_action_failed"
            )
        )
    ).scalar_one()
    assert event.body == {
        "adventurer": str(scenario.adventurer.id),
        "action": "candidate_a",
        "reason": "inventory_full",
    }


async def test_candidate_acquisition_clamps_hp_when_max_hp_decreases_but_max_mp_stays_fixed(
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
    """Per obsidian/.../キャラクター/ステータス.md section 5: max MP is
    fixed at 100 for every combatant and is never affected by acquired
    items, unlike max HP."""
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    draining_item = await item_factory(
        granted_spell_id=spell.id,
        base_stat_modifiers={"max_hp": -400},
    )
    other_candidate = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=draining_item.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=other_candidate.id)

    run = await run_factory(state=RunState.CAMP, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id, hp=500, mp=100)
    camp = await camp_factory(
        run_id=run.id,
        spirit_id=spirit.id,
        candidate_a_item_id=draining_item.id,
        candidate_b_item_id=other_candidate.id,
        floor=1,
    )
    await camp_member_factory(camp_id=camp.id, run_adventurer_id=adventurer.id)
    scenario = SimpleNamespace(run=run, adventurer=adventurer)

    outcome = await _select(db_session, scenario, 2)

    assert outcome.processed is True
    # base_max_hp=500 + (-400) = 100; hp was 500 -> clamped down to 100
    assert adventurer.hp == 100
    # max MP is fixed at 100 regardless of items; mp was already 100
    assert adventurer.mp == 100


async def test_duplicate_candidate_succeeds_even_when_inventory_full(
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
    scenario = await _setup_camp(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )
    await inventory_item_factory(
        scenario.adventurer.id, scenario.candidate_a.id, slot=1, current_level=1
    )
    for slot in range(2, MAX_SLOTS + 1):
        filler = await item_factory(granted_spell_id=scenario.spell.id)
        await inventory_item_factory(scenario.adventurer.id, filler.id, slot=slot)

    outcome = await _select(db_session, scenario, 2)

    assert outcome.processed is True

    row = (
        await db_session.execute(
            select(RunAdventurerItem).where(
                RunAdventurerItem.run_adventurer_id == scenario.adventurer.id,
                RunAdventurerItem.item_id == scenario.candidate_a.id,
            )
        )
    ).scalar_one()
    assert row.current_level == 6


async def test_forge_increases_level_for_matching_attribute_items(
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
    scenario = await _setup_camp(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        representative_attribute="RR",
    )
    matching = await item_factory(granted_spell_id=scenario.spell.id, attribute="RR")
    other = await item_factory(granted_spell_id=scenario.spell.id, attribute="BB")
    await inventory_item_factory(scenario.adventurer.id, matching.id, slot=1, current_level=1)
    await inventory_item_factory(scenario.adventurer.id, other.id, slot=2, current_level=1)

    outcome = await _select(db_session, scenario, 4)

    assert outcome.processed is True
    assert scenario.member.selected_action == "forge"

    rows = {
        row.item_id: row.current_level
        for row in (
            await db_session.execute(
                select(RunAdventurerItem).where(
                    RunAdventurerItem.run_adventurer_id == scenario.adventurer.id
                )
            )
        )
        .scalars()
        .all()
    }
    assert rows[matching.id] == 2
    assert rows[other.id] == 1


async def test_forge_includes_blessing_item(
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
    scenario = await _setup_camp(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        representative_attribute="RR",
    )
    await inventory_item_factory(
        scenario.adventurer.id, scenario.blessing_item.id, slot=1, current_level=2
    )

    await _select(db_session, scenario, 4)

    row = (
        await db_session.execute(
            select(RunAdventurerItem).where(
                RunAdventurerItem.run_adventurer_id == scenario.adventurer.id,
                RunAdventurerItem.item_id == scenario.blessing_item.id,
            )
        )
    ).scalar_one()
    assert row.current_level == 3


async def test_forge_with_zero_matches_still_succeeds(
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
    scenario = await _setup_camp(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        representative_attribute="RR",
    )
    other = await item_factory(granted_spell_id=scenario.spell.id, attribute="BB")
    await inventory_item_factory(scenario.adventurer.id, other.id, slot=1, current_level=1)

    outcome = await _select(db_session, scenario, 4)

    assert outcome.processed is True
    assert scenario.member.selected_action == "forge"

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == scenario.run.id, RunEvent.event_type == "camp_action_selected"
            )
        )
    ).scalar_one()
    assert event.body == {
        "adventurer": str(scenario.adventurer.id),
        "action": "forge",
        "affected_count": 0,
    }


async def test_second_selection_after_success_is_rejected(
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
    scenario = await _setup_camp(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
    )

    first = await _select(db_session, scenario, 1)
    second = await _select(db_session, scenario, 4)

    assert first.processed is True
    assert second.processed is False
    assert second.reason == ACTION_ALREADY_SELECTED


async def test_select_rejected_when_not_in_camp(db_session, run_factory, adventurer_factory):
    run = await run_factory(state=RunState.BATTLE, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id)

    outcome = await handle_select(
        Select(value=1),
        _context(db_session, run.id, adventurer.youtube_id, "@select 1"),
    )

    assert outcome.processed is False
    assert outcome.reason == "not_in_camp"


async def test_select_rejected_when_viewer_not_joined(
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

    outcome = await handle_select(
        Select(value=1),
        _context(db_session, run.id, "someone_who_never_joined", "@select 1"),
    )

    assert outcome.processed is False
    assert outcome.reason == "not_joined"


async def test_select_rejected_when_cannot_select_action(
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
    scenario = await _setup_camp(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        can_select_action=False,
    )

    outcome = await _select(db_session, scenario, 1)

    assert outcome.processed is False
    assert outcome.reason == ACTION_NOT_AVAILABLE


async def _commit_camp_scenario() -> SimpleNamespace:
    async with async_session_factory() as session:
        spell = Spell(
            command=_unique("spell"),
            display_name="s",
            attribute="RR",
            mp_cost=0,
            target_rule="single_enemy",
            effects=[{"type": "damage", "power": 1}],
        )
        session.add(spell)
        await session.flush()

        blessing_item = Item(
            item_key=_unique("item"), display_name="b", attribute="RR", granted_spell_id=spell.id
        )
        session.add(blessing_item)
        await session.flush()

        spirit = Spirit(
            spirit_key=_unique("spirit"),
            display_name="s",
            representative_attribute="RR",
            blessing_item_id=blessing_item.id,
        )
        session.add(spirit)
        await session.flush()

        candidate_a = Item(
            item_key=_unique("item"), display_name="a", attribute="RR", granted_spell_id=spell.id
        )
        candidate_b = Item(
            item_key=_unique("item"), display_name="b", attribute="RR", granted_spell_id=spell.id
        )
        session.add_all([candidate_a, candidate_b])
        await session.flush()

        session.add(SpiritItemPoolEntry(spirit_id=spirit.id, item_id=candidate_a.id))
        session.add(SpiritItemPoolEntry(spirit_id=spirit.id, item_id=candidate_b.id))

        run = Run(state=RunState.CAMP, current_floor=1)
        session.add(run)
        await session.flush()

        adventurer = RunAdventurer(run_id=run.id, youtube_id=_unique("viewer"), hp=500, mp=100)
        session.add(adventurer)
        await session.flush()

        camp = RunCamp(
            run_id=run.id,
            floor=1,
            spirit_id=spirit.id,
            candidate_a_item_id=candidate_a.id,
            candidate_b_item_id=candidate_b.id,
            started_at=NOW,
            deadline_at=NOW + timedelta(minutes=5),
        )
        session.add(camp)
        await session.flush()

        session.add(
            RunCampMember(
                camp_id=camp.id,
                run_adventurer_id=adventurer.id,
                can_select_action=True,
            )
        )
        await session.commit()

        return SimpleNamespace(
            run_id=run.id,
            camp_id=camp.id,
            adventurer_id=adventurer.id,
            viewer_id=adventurer.youtube_id,
        )


async def _commit_camp_scenario_with_two_adventurers() -> SimpleNamespace:
    """Builds the scenario through the real start_camp() Use Case (not a
    hand-built RunCamp) so a camp_started event already occupies sequence
    1 before the concurrent selections run -- matching how CAMP actually
    starts in production, where camp_action_selected events are never the
    first events on a run."""
    async with async_session_factory() as session:
        spell = Spell(
            command=_unique("spell"),
            display_name="s",
            attribute="RR",
            mp_cost=0,
            target_rule="single_enemy",
            effects=[{"type": "damage", "power": 1}],
        )
        session.add(spell)
        await session.flush()

        blessing_item = Item(
            item_key=_unique("item"), display_name="b", attribute="RR", granted_spell_id=spell.id
        )
        session.add(blessing_item)
        await session.flush()

        spirit = Spirit(
            spirit_key=_unique("spirit"),
            display_name="s",
            representative_attribute="RR",
            blessing_item_id=blessing_item.id,
        )
        session.add(spirit)
        await session.flush()

        candidate_a = Item(
            item_key=_unique("item"), display_name="a", attribute="RR", granted_spell_id=spell.id
        )
        candidate_b = Item(
            item_key=_unique("item"), display_name="b", attribute="RR", granted_spell_id=spell.id
        )
        session.add_all([candidate_a, candidate_b])
        await session.flush()

        session.add(SpiritItemPoolEntry(spirit_id=spirit.id, item_id=candidate_a.id))
        session.add(SpiritItemPoolEntry(spirit_id=spirit.id, item_id=candidate_b.id))

        run = Run(state=RunState.BATTLE, current_floor=1)
        session.add(run)
        await session.flush()

        adventurer_1 = RunAdventurer(run_id=run.id, youtube_id=_unique("viewer"), hp=500, mp=100)
        adventurer_2 = RunAdventurer(run_id=run.id, youtube_id=_unique("viewer"), hp=500, mp=100)
        session.add_all([adventurer_1, adventurer_2])
        await session.flush()

        # start_camp() registers both already-participating adventurers as
        # members with can_select_action=True and records camp_started.
        await start_camp(session, run.id, spirit.id, now=NOW, random_source=random.Random(1))
        await session.commit()

        return SimpleNamespace(
            run_id=run.id,
            adventurer_1_id=adventurer_1.id,
            adventurer_2_id=adventurer_2.id,
            viewer_1_id=adventurer_1.youtube_id,
            viewer_2_id=adventurer_2.youtube_id,
        )


async def test_concurrent_different_adventurers_both_selections_succeed_with_sequential_events():
    """Two different adventurers selecting concurrently must not deadlock,
    must both succeed, and must each get their own event with a unique,
    run-scoped monotonically increasing sequence -- proving append_event's
    MAX(sequence)+1 allocation under the run-row lock serializes correctly
    across concurrent transactions, not just across concurrent attempts by
    the same adventurer, and that it continues correctly from whatever
    sequence camp_started already left the run at (it does not start over
    at 1 just because the two concurrent events happen to be the next
    ones recorded)."""
    scenario = await _commit_camp_scenario_with_two_adventurers()

    async with async_session_factory() as session:
        baseline = (
            await session.execute(
                select(func.max(RunEvent.sequence)).where(RunEvent.run_id == scenario.run_id)
            )
        ).scalar_one()
    # camp_started is the only event recorded by start_camp(), so the
    # baseline here is 1 -- captured dynamically rather than assumed, so
    # this test keeps working if start_camp() ever records more events.
    assert baseline == 1

    async def _submit(viewer_id: str, raw_text: str):
        async with async_session_factory() as session:
            command_input = CommandInput(
                source="youtube_live",
                source_message_id=_unique("race-msg"),
                viewer_id=viewer_id,
                viewer_display_name="viewer",
                raw_text=raw_text,
                received_at=NOW,
            )
            return await submit_command(
                session, scenario.run_id, command_input, handlers=build_camp_handlers()
            )

    first, second = await asyncio.gather(
        _submit(scenario.viewer_1_id, "@select 1"),
        _submit(scenario.viewer_2_id, "@select 1"),
    )

    assert first.processed is True
    assert second.processed is True

    async with async_session_factory() as session:
        selected_events = (
            (
                await session.execute(
                    select(RunEvent)
                    .where(
                        RunEvent.run_id == scenario.run_id,
                        RunEvent.event_type == "camp_action_selected",
                    )
                    .order_by(RunEvent.sequence)
                )
            )
            .scalars()
            .all()
        )
        all_events = (
            (
                await session.execute(
                    select(RunEvent)
                    .where(RunEvent.run_id == scenario.run_id)
                    .order_by(RunEvent.sequence)
                )
            )
            .scalars()
            .all()
        )

    assert len(selected_events) == 2
    sequences = [event.sequence for event in selected_events]
    assert sequences == [baseline + 1, baseline + 2]
    adventurers = {event.body["adventurer"] for event in selected_events}
    assert adventurers == {str(scenario.adventurer_1_id), str(scenario.adventurer_2_id)}

    # the run's full event history (camp_started + the two selections) has
    # no duplicate or out-of-order sequence numbers
    all_sequences = [event.sequence for event in all_events]
    assert all_sequences == [1, 2, 3]


async def test_concurrent_different_messages_only_one_selection_succeeds():
    scenario = await _commit_camp_scenario()

    async def _submit(raw_text: str):
        async with async_session_factory() as session:
            command_input = CommandInput(
                source="youtube_live",
                source_message_id=_unique("race-msg"),
                viewer_id=scenario.viewer_id,
                viewer_display_name="viewer",
                raw_text=raw_text,
                received_at=NOW,
            )
            return await submit_command(
                session, scenario.run_id, command_input, handlers=build_camp_handlers()
            )

    first, second = await asyncio.gather(_submit("@select 1"), _submit("@select 4"))

    outcomes = {first.reason, second.reason}
    assert None in outcomes
    assert ACTION_ALREADY_SELECTED in outcomes

    async with async_session_factory() as session:
        member = await get_camp_member(session, scenario.camp_id, scenario.adventurer_id)
        assert member.selected_action is not None


async def test_duplicate_source_message_id_does_not_double_apply():
    scenario = await _commit_camp_scenario()

    command_input = CommandInput(
        source="youtube_live",
        source_message_id=_unique("dup-msg"),
        viewer_id=scenario.viewer_id,
        viewer_display_name="viewer",
        raw_text="@select 1",
        received_at=NOW,
    )

    async with async_session_factory() as session:
        first = await submit_command(
            session, scenario.run_id, command_input, handlers=build_camp_handlers()
        )
    async with async_session_factory() as session:
        second = await submit_command(
            session, scenario.run_id, command_input, handlers=build_camp_handlers()
        )

    assert first.id == second.id
    assert first.processed is True
    assert first.reason is None

    async with async_session_factory() as session:
        count = (
            await session.execute(
                select(func.count())
                .select_from(ProcessedCommand)
                .where(ProcessedCommand.source_message_id == command_input.source_message_id)
            )
        ).scalar_one()
    assert count == 1
