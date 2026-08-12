import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from yt_live_dungeon.domain.errors import CampConfigurationError
from yt_live_dungeon.features.camp.start import start_camp
from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Item,
    Run,
    RunAdventurer,
    RunCamp,
    RunCampMember,
    RunEvent,
    RunState,
    Spell,
    Spirit,
    SpiritItemPoolEntry,
)
from yt_live_dungeon.persistence.queries.camp import get_camp_by_run_and_floor
from yt_live_dungeon.persistence.queries.spirit import list_active_pool_item_ids


async def _setup_spirit_with_pool(
    spell_factory, item_factory, spirit_factory, pool_entry_factory, pool_size: int = 2
):
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)

    pool_item_ids = []
    for _ in range(pool_size):
        pool_item = await item_factory(granted_spell_id=spell.id)
        await pool_entry_factory(spirit_id=spirit.id, item_id=pool_item.id)
        pool_item_ids.append(pool_item.id)

    return spirit, pool_item_ids


NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def test_starts_camp_from_battle_run(
    db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory
):
    spirit, _pool_ids = await _setup_spirit_with_pool(
        spell_factory, item_factory, spirit_factory, pool_entry_factory
    )
    run = await run_factory(state=RunState.BATTLE, current_floor=3)

    camp = await start_camp(
        db_session, run.id, spirit.id, now=NOW, random_source=random.Random(1)
    )

    assert camp.run_id == run.id
    assert camp.floor == 3
    assert run.state == RunState.CAMP


async def test_deadline_is_five_minutes_after_start(
    db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory
):
    spirit, _pool_ids = await _setup_spirit_with_pool(
        spell_factory, item_factory, spirit_factory, pool_entry_factory
    )
    run = await run_factory()

    camp = await start_camp(
        db_session, run.id, spirit.id, now=NOW, random_source=random.Random(1)
    )

    assert camp.started_at == NOW
    assert camp.deadline_at == NOW + timedelta(minutes=5)


async def test_candidates_are_two_distinct_items(
    db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory
):
    spirit, pool_ids = await _setup_spirit_with_pool(
        spell_factory, item_factory, spirit_factory, pool_entry_factory, pool_size=4
    )
    run = await run_factory()

    camp = await start_camp(
        db_session, run.id, spirit.id, now=NOW, random_source=random.Random(7)
    )

    assert camp.candidate_a_item_id != camp.candidate_b_item_id
    assert camp.candidate_a_item_id in pool_ids
    assert camp.candidate_b_item_id in pool_ids


async def test_candidates_are_reproducible_with_fixed_random_seed(
    db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory
):
    spirit, pool_ids = await _setup_spirit_with_pool(
        spell_factory, item_factory, spirit_factory, pool_entry_factory, pool_size=5
    )
    run_a = await run_factory()
    run_b = await run_factory()

    camp_a = await start_camp(
        db_session, run_a.id, spirit.id, now=NOW, random_source=random.Random(42)
    )
    camp_b = await start_camp(
        db_session, run_b.id, spirit.id, now=NOW, random_source=random.Random(42)
    )

    assert camp_a.candidate_a_item_id == camp_b.candidate_a_item_id
    assert camp_a.candidate_b_item_id == camp_b.candidate_b_item_id


async def test_pool_excludes_items_from_other_spirits(
    db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory
):
    spell = await spell_factory()
    blessing_a = await item_factory(granted_spell_id=spell.id)
    spirit_a = await spirit_factory(blessing_item_id=blessing_a.id)
    blessing_b = await item_factory(granted_spell_id=spell.id)
    spirit_b = await spirit_factory(blessing_item_id=blessing_b.id)

    item_for_a = await item_factory(granted_spell_id=spell.id)
    item_for_b = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(spirit_id=spirit_a.id, item_id=item_for_a.id)
    await pool_entry_factory(spirit_id=spirit_b.id, item_id=item_for_b.id)

    pool_ids = await list_active_pool_item_ids(db_session, spirit_a.id)

    assert pool_ids == [item_for_a.id]


async def test_pool_excludes_inactive_items(
    db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory
):
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)

    active_item = await item_factory(granted_spell_id=spell.id, is_active=True)
    inactive_item = await item_factory(granted_spell_id=spell.id, is_active=False)
    await pool_entry_factory(spirit_id=spirit.id, item_id=active_item.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=inactive_item.id)

    pool_ids = await list_active_pool_item_ids(db_session, spirit.id)

    assert pool_ids == [active_item.id]


async def test_pool_item_ids_are_returned_in_deterministic_ascending_order(
    db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory
):
    """The candidate draw feeds this list straight into a seeded
    RandomSource.sample(); without an explicit ORDER BY the draw would
    depend on Postgres's unspecified physical row order instead of the
    seed alone."""
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)

    items = [await item_factory(granted_spell_id=spell.id) for _ in range(4)]
    for item in reversed(items):
        await pool_entry_factory(spirit_id=spirit.id, item_id=item.id)

    pool_ids = await list_active_pool_item_ids(db_session, spirit.id)

    assert pool_ids == sorted(item.id for item in items)


async def test_rerunning_for_same_run_and_floor_is_idempotent(
    db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory
):
    spirit, _pool_ids = await _setup_spirit_with_pool(
        spell_factory, item_factory, spirit_factory, pool_entry_factory
    )
    run = await run_factory()
    adventurer = RunAdventurer(run_id=run.id, youtube_id="v1", hp=500, mp=100)
    db_session.add(adventurer)
    await db_session.flush()

    first = await start_camp(
        db_session, run.id, spirit.id, now=NOW, random_source=random.Random(1)
    )
    second = await start_camp(
        db_session, run.id, spirit.id, now=NOW, random_source=random.Random(999)
    )

    assert first.id == second.id
    assert first.candidate_a_item_id == second.candidate_a_item_id
    assert first.candidate_b_item_id == second.candidate_b_item_id

    member_count = (
        await db_session.execute(
            select(func.count()).select_from(RunCampMember).where(RunCampMember.camp_id == first.id)
        )
    ).scalar_one()
    assert member_count == 1

    event_count = (
        await db_session.execute(
            select(func.count())
            .select_from(RunEvent)
            .where(RunEvent.run_id == run.id, RunEvent.event_type == "camp_started")
        )
    ).scalar_one()
    assert event_count == 1


async def test_raises_when_pool_has_fewer_than_two_items(
    db_session, spell_factory, item_factory, spirit_factory, run_factory
):
    spell = await spell_factory()
    blessing_item = await item_factory(granted_spell_id=spell.id)
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    run = await run_factory()

    with pytest.raises(CampConfigurationError):
        await start_camp(db_session, run.id, spirit.id, now=NOW, random_source=random.Random(1))

    camp_count = (
        await db_session.execute(
            select(func.count()).select_from(RunCamp).where(RunCamp.run_id == run.id)
        )
    ).scalar_one()
    assert camp_count == 0

    event_count = (
        await db_session.execute(
            select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run.id)
        )
    ).scalar_one()
    assert event_count == 0


async def test_only_alive_and_participating_adventurers_become_members(
    db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory
):
    spirit, _pool_ids = await _setup_spirit_with_pool(
        spell_factory, item_factory, spirit_factory, pool_entry_factory
    )
    run = await run_factory()

    active = RunAdventurer(run_id=run.id, youtube_id="active", hp=500, mp=100)
    dead = RunAdventurer(
        run_id=run.id, youtube_id="dead", hp=0, mp=100, is_alive=False, is_participating=True
    )
    logged_out = RunAdventurer(
        run_id=run.id, youtube_id="left", hp=500, mp=100, is_alive=True, is_participating=False
    )
    db_session.add_all([active, dead, logged_out])
    await db_session.flush()

    camp = await start_camp(
        db_session, run.id, spirit.id, now=NOW, random_source=random.Random(1)
    )

    members = (
        await db_session.execute(
            select(RunCampMember).where(RunCampMember.camp_id == camp.id)
        )
    ).scalars().all()

    assert {m.run_adventurer_id for m in members} == {active.id}


async def test_camp_start_members_have_can_select_action_true(
    db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory
):
    spirit, _pool_ids = await _setup_spirit_with_pool(
        spell_factory, item_factory, spirit_factory, pool_entry_factory
    )
    run = await run_factory()
    adventurer = RunAdventurer(run_id=run.id, youtube_id="v1", hp=500, mp=100)
    db_session.add(adventurer)
    await db_session.flush()

    camp = await start_camp(
        db_session, run.id, spirit.id, now=NOW, random_source=random.Random(1)
    )

    member = (
        await db_session.execute(
            select(RunCampMember).where(
                RunCampMember.camp_id == camp.id, RunCampMember.run_adventurer_id == adventurer.id
            )
        )
    ).scalar_one()

    assert member.can_select_action is True
    assert member.selected_action is None
    assert member.ready_at is None
    assert member.left_at is None


async def test_camp_started_event_is_recorded(
    db_session, spell_factory, item_factory, spirit_factory, pool_entry_factory, run_factory
):
    spirit, _pool_ids = await _setup_spirit_with_pool(
        spell_factory, item_factory, spirit_factory, pool_entry_factory
    )
    run = await run_factory()

    camp = await start_camp(
        db_session, run.id, spirit.id, now=NOW, random_source=random.Random(1)
    )

    event = (
        await db_session.execute(
            select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.event_type == "camp_started")
        )
    ).scalar_one()

    assert event.body["floor"] == camp.floor
    assert event.body["spirit_id"] == spirit.id
    assert event.body["candidate_a_item_id"] == camp.candidate_a_item_id
    assert event.body["candidate_b_item_id"] == camp.candidate_b_item_id
    assert event.body["deadline_at"] == camp.deadline_at.isoformat()
    assert event.sequence == 1


async def test_concurrent_start_camp_calls_for_same_run_and_floor_produce_one_camp():
    """The run row's FOR UPDATE lock -- not application-level checks --
    is what prevents two concurrent start_camp() calls from creating two
    camps for the same (run, floor)."""
    async with async_session_factory() as setup_session:
        spell = Spell(
            command=f"spell-{uuid.uuid4().hex[:8]}",
            display_name="s",
            attribute="RR",
            mp_cost=0,
            target_rule="single_enemy",
            effects=[{"type": "damage", "power": 1}],
        )
        setup_session.add(spell)
        await setup_session.flush()

        blessing_item = Item(
            item_key=f"item-{uuid.uuid4().hex[:8]}",
            display_name="blessing",
            attribute="RR",
            granted_spell_id=spell.id,
        )
        setup_session.add(blessing_item)
        await setup_session.flush()

        spirit = Spirit(
            spirit_key=f"spirit-{uuid.uuid4().hex[:8]}",
            display_name="s",
            representative_attribute="RR",
            blessing_item_id=blessing_item.id,
        )
        setup_session.add(spirit)
        await setup_session.flush()

        for _ in range(2):
            pool_item = Item(
                item_key=f"item-{uuid.uuid4().hex[:8]}",
                display_name="pool",
                attribute="RR",
                granted_spell_id=spell.id,
            )
            setup_session.add(pool_item)
            await setup_session.flush()
            setup_session.add(SpiritItemPoolEntry(spirit_id=spirit.id, item_id=pool_item.id))

        run = Run(state=RunState.BATTLE, current_floor=1)
        setup_session.add(run)
        await setup_session.commit()
        await setup_session.refresh(run)

        spirit_id = spirit.id
        run_id = run.id

    async def _start() -> uuid.UUID:
        async with async_session_factory() as session:
            camp = await start_camp(
                session, run_id, spirit_id, now=NOW, random_source=random.Random(1)
            )
            await session.commit()
            return camp.id

    first_id, second_id = await asyncio.gather(_start(), _start())

    assert first_id == second_id

    async with async_session_factory() as session:
        camp = await get_camp_by_run_and_floor(session, run_id, 1)
        assert camp is not None
        assert camp.id == first_id
