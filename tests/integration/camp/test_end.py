import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from yt_live_dungeon.domain.errors import InvalidStatModifierError
from yt_live_dungeon.features.camp.end import end_camp
from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Egregore,
    EgregoreItemPoolEntry,
    Enemy,
    EnemyGroup,
    EnemyGroupMember,
    Item,
    Run,
    RunAdventurer,
    RunAdventurerItem,
    RunCamp,
    RunCampMember,
    RunEvent,
    RunState,
    Spell,
)
from yt_live_dungeon.persistence.queries.camp import get_open_camp

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


async def _setup_camp(
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
    camp = await camp_factory(
        run_id=run.id,
        egregore_id=egregore.id,
        candidate_a_item_id=candidate_a.id,
        candidate_b_item_id=candidate_b.id,
        floor=1,
    )
    return run, camp


async def test_end_camp_is_idempotent_when_already_ended(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory,
    camp_factory,
):
    run, camp = await _setup_camp(
        spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory, camp_factory
    )
    camp.ended_at = NOW

    await end_camp(
        db_session, run, camp, now=NOW, reason="all_ready", random_source=random.Random(1)
    )

    count = (
        await db_session.execute(
            select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.event_type == "camp_ended")
        )
    ).scalars().all()
    assert count == []
    await db_session.refresh(run)
    assert run.state == RunState.CAMP


async def test_end_camp_retires_when_no_participants(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory,
    camp_factory,
):
    run, camp = await _setup_camp(
        spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory, camp_factory
    )

    await end_camp(db_session, run, camp, now=NOW, reason="empty", random_source=random.Random(1))

    assert camp.ended_at == NOW
    assert run.state == RunState.RETIRE
    assert run.ended_at == NOW


async def test_end_camp_starts_next_floor_when_participants_remain(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory,
    camp_factory, adventurer_factory, enemy_factory, enemy_group_factory,
):
    run, camp = await _setup_camp(
        spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory, camp_factory
    )
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run.next_group_id = group.id
    await adventurer_factory(run_id=run.id, hp=200, mp=10)

    await end_camp(
        db_session, run, camp, now=NOW, reason="all_ready", random_source=random.Random(1)
    )

    assert camp.ended_at == NOW
    assert run.state == RunState.BATTLE
    assert run.current_floor == 2


async def test_end_camp_records_camp_ended_event_with_reason_and_participant_count(
    db_session, spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory,
    camp_factory, adventurer_factory, enemy_factory, enemy_group_factory,
):
    run, camp = await _setup_camp(
        spell_factory, item_factory, egregore_factory, pool_entry_factory, run_factory, camp_factory
    )
    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )
    run.next_group_id = group.id
    await adventurer_factory(run_id=run.id)
    await adventurer_factory(run_id=run.id)

    await end_camp(
        db_session, run, camp, now=NOW, reason="all_ready", random_source=random.Random(1)
    )

    event = (
        await db_session.execute(
            select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.event_type == "camp_ended")
        )
    ).scalar_one()
    assert event.body == {"floor": 1, "reason": "all_ready", "participant_count": 2}


async def test_floor_generation_failure_does_not_leave_camp_ended_alone():
    """Proves the atomicity requirement at the DB level: if starting the
    next floor raises partway through (here, because a participant owns
    an item with malformed stat modifiers), the CAMP-ending mutations
    made earlier in the same call must not survive on their own -- since
    nothing here commits, only the caller (a real handler's single
    submit_command() commit) ever would, and that never happens because
    the exception propagates first."""
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

        egregore = Egregore(
            egregore_key=_unique("egregore"),
            display_name="s",
            representative_attribute="RR",
            blessing_item_id=blessing_item.id,
        )
        session.add(egregore)
        await session.flush()

        candidate_a = Item(
            item_key=_unique("item"), display_name="a", attribute="RR", granted_spell_id=spell.id
        )
        candidate_b = Item(
            item_key=_unique("item"), display_name="b", attribute="RR", granted_spell_id=spell.id
        )
        # an item with an invalid stat modifier key -- calculate_final_stats
        # rejects this when recomputing max MP during floor start
        broken_item = Item(
            item_key=_unique("item"),
            display_name="broken",
            attribute="RR",
            granted_spell_id=spell.id,
            base_stat_modifiers={"not_a_real_stat": 1},
        )
        session.add_all([candidate_a, candidate_b, broken_item])
        await session.flush()
        session.add(EgregoreItemPoolEntry(egregore_id=egregore.id, item_id=candidate_a.id))
        session.add(EgregoreItemPoolEntry(egregore_id=egregore.id, item_id=candidate_b.id))

        enemy = Enemy(
            enemy_key=_unique("enemy"),
            display_name="e",
            base_max_hp=100,
            base_max_mp=100,
            base_attributes={},
            break_max=50,
        )
        session.add(enemy)
        await session.flush()
        enemy_group = EnemyGroup(group_key=_unique("group"), display_name="g")
        session.add(enemy_group)
        await session.flush()
        session.add(
            EnemyGroupMember(
                group_id=enemy_group.id, order_in_group=1, enemy_id=enemy.id, role="master"
            )
        )
        await session.flush()

        run = Run(state=RunState.CAMP, current_floor=1, next_group_id=enemy_group.id)
        session.add(run)
        await session.flush()

        adventurer = RunAdventurer(run_id=run.id, youtube_id=_unique("viewer"), hp=500, mp=100)
        session.add(adventurer)
        await session.flush()
        session.add(
            RunAdventurerItem(
                run_adventurer_id=adventurer.id,
                item_id=broken_item.id,
                slot=1,
                current_level=1,
                acquired_floor=1,
            )
        )

        camp = RunCamp(
            run_id=run.id,
            floor=1,
            egregore_id=egregore.id,
            candidate_a_item_id=candidate_a.id,
            candidate_b_item_id=candidate_b.id,
            started_at=NOW,
            deadline_at=NOW + timedelta(minutes=5),
        )
        session.add(camp)
        await session.flush()
        session.add(
            RunCampMember(camp_id=camp.id, run_adventurer_id=adventurer.id, can_select_action=True)
        )
        await session.commit()

        run_id = run.id

    async with async_session_factory() as session:
        run = await session.get(Run, run_id, with_for_update=True)
        camp = await get_open_camp(session, run_id, run.current_floor)

        with pytest.raises(InvalidStatModifierError):
            await end_camp(
                session, run, camp, now=NOW, reason="all_ready", random_source=random.Random(1)
            )

        # deliberately never commits -- mirrors the exception propagating
        # out of a real handler before submit_command()'s single commit()
        await session.rollback()

    async with async_session_factory() as verify_session:
        fresh_camp = await get_open_camp(verify_session, run_id, 1)
        assert fresh_camp is not None
        assert fresh_camp.ended_at is None

        fresh_run = await verify_session.get(Run, run_id)
        assert fresh_run.state == RunState.CAMP
        assert fresh_run.current_floor == 1
