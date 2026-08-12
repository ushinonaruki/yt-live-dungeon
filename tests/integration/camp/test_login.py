import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from yt_live_dungeon.domain.errors import LoginConfigurationError
from yt_live_dungeon.features.camp.handlers import build_camp_handlers
from yt_live_dungeon.features.camp.login import (
    ALREADY_JOINED,
    MAX_PARTICIPANTS,
    PARTY_FULL,
    handle_login,
)
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.parse import Login
from yt_live_dungeon.features.commands.submit import submit_command
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Item,
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


class _ExplodingRandomSource:
    """A RandomSource stub that fails the test if it is ever consulted --
    used to prove a rejected login never draws randomness."""

    def sample(self, population, k):
        raise AssertionError("random_source.sample() must not be called")


def _context(session, run_id, viewer_id: str, *, random_source=None) -> CommandContext:
    return CommandContext(
        session=session,
        run_id=run_id,
        command_input=CommandInput(
            source="youtube_live",
            source_message_id=_unique("msg"),
            viewer_id=viewer_id,
            viewer_display_name="viewer",
            raw_text="@login",
            received_at=NOW,
        ),
        random_source=random_source if random_source is not None else random.Random(1),
    )


async def _isolate_spirit_draw(db_session, spirit_id) -> None:
    """@login draws uniformly from *every* active spirit visible in this
    transaction. The shared test DB is never reset between tests, so
    other tests' committed spirits (real-commit concurrency scenarios,
    seed data) would otherwise also be in that population, making a
    seeded RandomSource's draw depend on what ran earlier instead of
    being deterministic. Deactivating every other spirit only inside
    this test's own (rolled-back) transaction fixes that without
    touching real committed state."""
    await db_session.execute(update(Spirit).where(Spirit.id != spirit_id).values(is_active=False))


async def _setup_open_camp(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
):
    """A CAMP whose spirit has one active pool item (for @login's own
    draw) plus two unrelated candidate items (for the RunCamp row's own
    candidate_a/candidate_b, which @login never touches)."""
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    pool_item = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=pool_item.id)
    await _isolate_spirit_draw(db_session, spirit.id)

    candidate_a = await item_factory(granted_spell_id=spell.id)
    candidate_b = await item_factory(granted_spell_id=spell.id)

    run = await run_factory(state=RunState.CAMP, current_floor=1)
    camp = await camp_factory(
        run_id=run.id,
        spirit_id=spirit.id,
        candidate_a_item_id=candidate_a.id,
        candidate_b_item_id=candidate_b.id,
        floor=1,
    )

    return spell, blessing_item, spirit, pool_item, run, camp


async def test_login_rejected_when_not_in_camp(db_session, run_factory):
    run = await run_factory(state=RunState.BATTLE, current_floor=1)

    outcome = await handle_login(Login(), _context(db_session, run.id, "viewer-1"))

    assert outcome.processed is False
    assert outcome.reason == "not_in_camp"


async def test_login_creates_new_adventurer_with_granted_items(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
):
    _spell, blessing_item, spirit, pool_item, run, _camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )

    outcome = await handle_login(
        Login(), _context(db_session, run.id, "new-viewer", random_source=random.Random(1))
    )

    assert outcome.processed is True

    adventurer = (
        await db_session.execute(
            select(RunAdventurer).where(
                RunAdventurer.run_id == run.id, RunAdventurer.youtube_id == "new-viewer"
            )
        )
    ).scalar_one()
    assert adventurer.spirit_id == spirit.id
    assert adventurer.is_alive is True
    assert adventurer.is_participating is True

    rows = (
        (
            await db_session.execute(
                select(RunAdventurerItem).where(
                    RunAdventurerItem.run_adventurer_id == adventurer.id
                )
            )
        )
        .scalars()
        .all()
    )
    item_ids = {row.item_id for row in rows}
    assert item_ids == {blessing_item.id, pool_item.id}
    assert all(row.current_level == 1 for row in rows)


async def test_login_new_adventurer_can_select_action_is_false(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
):
    _spell, _blessing, _spirit, _pool_item, run, camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )

    await handle_login(Login(), _context(db_session, run.id, "new-viewer"))

    adventurer = (
        await db_session.execute(
            select(RunAdventurer).where(
                RunAdventurer.run_id == run.id, RunAdventurer.youtube_id == "new-viewer"
            )
        )
    ).scalar_one()
    member = await get_camp_member(db_session, camp.id, adventurer.id)

    assert member.can_select_action is False
    assert member.selected_action is None
    assert member.ready_at is None


async def test_login_new_adventurer_hp_mp_reflect_granted_item_bonuses(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
):
    spell = await spell_factory()
    blessing_item = await item_factory(
        granted_spell_id=spell.id, base_stat_modifiers={"max_hp": 50, "max_mp": 10}
    )
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    pool_item = await item_factory(granted_spell_id=spell.id, base_stat_modifiers={"max_hp": 20})
    await pool_entry_factory(spirit_id=spirit.id, item_id=pool_item.id)
    await _isolate_spirit_draw(db_session, spirit.id)
    candidate_a = await item_factory(granted_spell_id=spell.id)
    candidate_b = await item_factory(granted_spell_id=spell.id)
    run = await run_factory(state=RunState.CAMP, current_floor=1)
    await camp_factory(
        run_id=run.id,
        spirit_id=spirit.id,
        candidate_a_item_id=candidate_a.id,
        candidate_b_item_id=candidate_b.id,
        floor=1,
    )

    await handle_login(Login(), _context(db_session, run.id, "new-viewer"))

    adventurer = (
        await db_session.execute(
            select(RunAdventurer).where(
                RunAdventurer.run_id == run.id, RunAdventurer.youtube_id == "new-viewer"
            )
        )
    ).scalar_one()

    assert adventurer.hp == 500 + 50 + 20
    assert adventurer.mp == 100 + 10


async def test_login_succeeds_from_seven_participants(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
    adventurer_factory,
    camp_member_factory,
):
    _spell, _blessing, _spirit, _pool_item, run, camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    for _ in range(7):
        existing = await adventurer_factory(run_id=run.id)
        await camp_member_factory(camp_id=camp.id, run_adventurer_id=existing.id)

    outcome = await handle_login(Login(), _context(db_session, run.id, "eighth-viewer"))

    assert outcome.processed is True


async def test_login_rejected_when_eight_participants(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
    adventurer_factory,
    camp_member_factory,
):
    _spell, _blessing, _spirit, _pool_item, run, camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    for _ in range(MAX_PARTICIPANTS):
        existing = await adventurer_factory(run_id=run.id)
        await camp_member_factory(camp_id=camp.id, run_adventurer_id=existing.id)

    outcome = await handle_login(Login(), _context(db_session, run.id, "ninth-viewer"))

    assert outcome.processed is False
    assert outcome.reason == PARTY_FULL


async def test_login_rejected_full_camp_does_not_consume_random_source(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
    adventurer_factory,
    camp_member_factory,
):
    _spell, _blessing, _spirit, _pool_item, run, camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    for _ in range(MAX_PARTICIPANTS):
        existing = await adventurer_factory(run_id=run.id)
        await camp_member_factory(camp_id=camp.id, run_adventurer_id=existing.id)

    outcome = await handle_login(
        Login(),
        _context(db_session, run.id, "ninth-viewer", random_source=_ExplodingRandomSource()),
    )

    assert outcome.processed is False
    assert outcome.reason == PARTY_FULL


async def test_login_rejected_full_camp_creates_no_adventurer_row(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
    adventurer_factory,
    camp_member_factory,
):
    _spell, _blessing, _spirit, _pool_item, run, camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    for _ in range(MAX_PARTICIPANTS):
        existing = await adventurer_factory(run_id=run.id)
        await camp_member_factory(camp_id=camp.id, run_adventurer_id=existing.id)

    await handle_login(Login(), _context(db_session, run.id, "ninth-viewer"))

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(RunAdventurer)
            .where(
                RunAdventurer.run_id == run.id, RunAdventurer.youtube_id == "ninth-viewer"
            )
        )
    ).scalar_one()
    assert count == 0


async def test_login_rejected_for_dead_adventurer_in_this_run(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
    adventurer_factory,
):
    _spell, _blessing, _spirit, _pool_item, run, _camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    await adventurer_factory(
        run_id=run.id,
        youtube_id="dead-viewer",
        is_alive=False,
        is_participating=False,
    )

    outcome = await handle_login(Login(), _context(db_session, run.id, "dead-viewer"))

    assert outcome.processed is False
    assert outcome.reason == ALREADY_JOINED


async def test_login_rejected_for_logged_out_adventurer_in_this_run(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
    adventurer_factory,
    camp_member_factory,
):
    _spell, _blessing, _spirit, _pool_item, run, camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    adventurer = await adventurer_factory(
        run_id=run.id, youtube_id="left-viewer", is_participating=False
    )
    await camp_member_factory(
        camp_id=camp.id, run_adventurer_id=adventurer.id, left_at=NOW
    )

    outcome = await handle_login(Login(), _context(db_session, run.id, "left-viewer"))

    assert outcome.processed is False
    assert outcome.reason == ALREADY_JOINED


async def test_login_rejected_for_logged_out_adventurer_does_not_consume_random_source(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
    adventurer_factory,
    camp_member_factory,
):
    _spell, _blessing, _spirit, _pool_item, run, camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    adventurer = await adventurer_factory(
        run_id=run.id, youtube_id="left-viewer", is_participating=False
    )
    await camp_member_factory(
        camp_id=camp.id, run_adventurer_id=adventurer.id, left_at=NOW
    )

    outcome = await handle_login(
        Login(),
        _context(db_session, run.id, "left-viewer", random_source=_ExplodingRandomSource()),
    )

    assert outcome.processed is False
    assert outcome.reason == ALREADY_JOINED


async def test_login_rejected_for_logged_out_adventurer_leaves_adventurer_state_untouched(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
    adventurer_factory,
    camp_member_factory,
    inventory_item_factory,
):
    spell, blessing_item, spirit, pool_item, run, camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    adventurer = await adventurer_factory(
        run_id=run.id,
        youtube_id="left-viewer",
        spirit_id=spirit.id,
        is_participating=False,
        hp=321,
        mp=45,
    )
    await inventory_item_factory(adventurer.id, blessing_item.id, slot=1, current_level=3)
    member = await camp_member_factory(
        camp_id=camp.id, run_adventurer_id=adventurer.id, left_at=NOW
    )

    await handle_login(Login(), _context(db_session, run.id, "left-viewer"))

    await db_session.refresh(adventurer)
    assert adventurer.is_participating is False
    assert adventurer.spirit_id == spirit.id
    assert adventurer.hp == 321
    assert adventurer.mp == 45

    rows = (
        await db_session.execute(
            select(RunAdventurerItem).where(
                RunAdventurerItem.run_adventurer_id == adventurer.id
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].item_id == blessing_item.id
    assert rows[0].current_level == 3

    await db_session.refresh(member)
    assert member.left_at == NOW


async def test_login_rejected_for_logged_out_adventurer_adds_no_rows_or_event(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
    adventurer_factory,
    camp_member_factory,
):
    _spell, _blessing, _spirit, _pool_item, run, camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    adventurer = await adventurer_factory(
        run_id=run.id, youtube_id="left-viewer", is_participating=False
    )
    await camp_member_factory(
        camp_id=camp.id, run_adventurer_id=adventurer.id, left_at=NOW
    )

    adventurer_count_before = (
        await db_session.execute(
            select(func.count()).select_from(RunAdventurer).where(RunAdventurer.run_id == run.id)
        )
    ).scalar_one()
    item_count_before = (
        await db_session.execute(
            select(func.count())
            .select_from(RunAdventurerItem)
            .where(RunAdventurerItem.run_adventurer_id == adventurer.id)
        )
    ).scalar_one()
    member_count_before = (
        await db_session.execute(
            select(func.count()).select_from(RunCampMember).where(RunCampMember.camp_id == camp.id)
        )
    ).scalar_one()

    await handle_login(Login(), _context(db_session, run.id, "left-viewer"))

    adventurer_count_after = (
        await db_session.execute(
            select(func.count()).select_from(RunAdventurer).where(RunAdventurer.run_id == run.id)
        )
    ).scalar_one()
    item_count_after = (
        await db_session.execute(
            select(func.count())
            .select_from(RunAdventurerItem)
            .where(RunAdventurerItem.run_adventurer_id == adventurer.id)
        )
    ).scalar_one()
    member_count_after = (
        await db_session.execute(
            select(func.count()).select_from(RunCampMember).where(RunCampMember.camp_id == camp.id)
        )
    ).scalar_one()
    event_count = (
        await db_session.execute(
            select(func.count())
            .select_from(RunEvent)
            .where(RunEvent.run_id == run.id, RunEvent.event_type == "adventurer_login")
        )
    ).scalar_one()

    assert adventurer_count_after == adventurer_count_before
    assert item_count_after == item_count_before
    assert member_count_after == member_count_before
    assert event_count == 0


async def test_login_by_a_different_new_viewer_can_use_the_slot_a_logout_freed(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
    adventurer_factory,
    camp_member_factory,
):
    _spell, _blessing, _spirit, _pool_item, run, camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    for _ in range(MAX_PARTICIPANTS - 1):
        existing = await adventurer_factory(run_id=run.id)
        await camp_member_factory(camp_id=camp.id, run_adventurer_id=existing.id)
    left_viewer_adventurer = await adventurer_factory(
        run_id=run.id, youtube_id="left-viewer", is_participating=False
    )
    await camp_member_factory(
        camp_id=camp.id, run_adventurer_id=left_viewer_adventurer.id, left_at=NOW
    )
    # participants are now MAX_PARTICIPANTS - 1 currently participating
    # (the logged-out one doesn't count), leaving exactly one open slot

    outcome = await handle_login(Login(), _context(db_session, run.id, "brand-new-viewer"))

    assert outcome.processed is True


async def test_login_rejected_when_already_joined(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
    adventurer_factory,
    camp_member_factory,
):
    _spell, _blessing, _spirit, _pool_item, run, camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    adventurer = await adventurer_factory(run_id=run.id, youtube_id="already-in")
    await camp_member_factory(camp_id=camp.id, run_adventurer_id=adventurer.id)

    outcome = await handle_login(Login(), _context(db_session, run.id, "already-in"))

    assert outcome.processed is False
    assert outcome.reason == ALREADY_JOINED


async def test_adventurer_login_event_body_for_new_adventurer(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    camp_factory,
):
    _spell, blessing_item, spirit, pool_item, run, _camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )

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
        "spirit": spirit.id,
        "blessing_item": blessing_item.id,
        "pool_item": pool_item.id,
    }


async def test_onboarding_raises_when_no_active_spirits(
    db_session, run_factory, camp_factory, spell_factory, item_factory, spirit_factory,
    pool_entry_factory,
):
    # a valid open camp requires a spirit, but that spirit need not be the
    # *only* spirit in master data, and it need not be active for a new
    # login to be attempted against it
    _spell, _blessing, spirit, _pool_item, run, _camp = await _setup_open_camp(
        db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory,
        camp_factory,
    )
    spirit.is_active = False
    await db_session.flush()

    with pytest.raises(LoginConfigurationError):
        await handle_login(Login(), _context(db_session, run.id, "new-viewer"))

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(RunAdventurer)
            .where(RunAdventurer.run_id == run.id, RunAdventurer.youtube_id == "new-viewer")
        )
    ).scalar_one()
    assert count == 0


async def _commit_open_camp_scenario(participant_count: int) -> dict:
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

        pool_item_a = Item(
            item_key=_unique("item"), display_name="pa", attribute="RR", granted_spell_id=spell.id
        )
        pool_item_b = Item(
            item_key=_unique("item"), display_name="pb", attribute="RR", granted_spell_id=spell.id
        )
        candidate_a = Item(
            item_key=_unique("item"), display_name="a", attribute="RR", granted_spell_id=spell.id
        )
        candidate_b = Item(
            item_key=_unique("item"), display_name="b", attribute="RR", granted_spell_id=spell.id
        )
        session.add_all([pool_item_a, pool_item_b, candidate_a, candidate_b])
        await session.flush()
        # this spirit is committed for real (unlike the rollback-scoped
        # fixtures elsewhere in this file), so it must satisfy the same
        # "at least 2 active pool items" invariant seed data does
        session.add(SpiritItemPoolEntry(spirit_id=spirit.id, item_id=pool_item_a.id))
        session.add(SpiritItemPoolEntry(spirit_id=spirit.id, item_id=pool_item_b.id))

        run = Run(state=RunState.CAMP, current_floor=1)
        session.add(run)
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

        for _ in range(participant_count):
            existing = RunAdventurer(run_id=run.id, youtube_id=_unique("viewer"), hp=500, mp=100)
            session.add(existing)
            await session.flush()
            session.add(
                RunCampMember(
                    camp_id=camp.id, run_adventurer_id=existing.id, can_select_action=True
                )
            )
        await session.commit()

        return {"run_id": run.id}


async def test_concurrent_logins_do_not_exceed_eight_participants():
    scenario = await _commit_open_camp_scenario(participant_count=7)

    async def _login(viewer_id: str):
        async with async_session_factory() as session:
            command_input = CommandInput(
                source="youtube_live",
                source_message_id=_unique("race-msg"),
                viewer_id=viewer_id,
                viewer_display_name="viewer",
                raw_text="@login",
                received_at=NOW,
            )
            return await submit_command(
                session,
                scenario["run_id"],
                command_input,
                handlers=build_camp_handlers(),
                random_source=random.Random(),
            )

    results = await asyncio.gather(
        _login(_unique("race-viewer")), _login(_unique("race-viewer"))
    )

    outcomes = {result.reason for result in results}
    assert None in outcomes
    assert PARTY_FULL in outcomes

    async with async_session_factory() as session:
        count = (
            await session.execute(
                select(func.count())
                .select_from(RunAdventurer)
                .where(
                    RunAdventurer.run_id == scenario["run_id"],
                    RunAdventurer.is_participating.is_(True),
                )
            )
        ).scalar_one()
    assert count == MAX_PARTICIPANTS
