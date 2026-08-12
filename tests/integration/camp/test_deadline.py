import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from yt_live_dungeon.features.camp.deadline import ensure_camp_deadline_evaluated
from yt_live_dungeon.persistence.models import RunEvent, RunState
from yt_live_dungeon.persistence.queries.camp import get_camp_member

STARTED_AT = datetime(2026, 1, 1, tzinfo=UTC)
DEADLINE_AT = STARTED_AT + timedelta(minutes=5)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


async def _setup_camp_with_members(
    spell_factory,
    item_factory,
    spirit_factory,
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
    spirit = await spirit_factory(blessing_item_id=blessing_item.id)
    candidate_a = await item_factory(granted_spell_id=spell.id)
    candidate_b = await item_factory(granted_spell_id=spell.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_a.id)
    await pool_entry_factory(spirit_id=spirit.id, item_id=candidate_b.id)

    enemy = await enemy_factory()
    group = await enemy_group_factory(
        members=[{"order_in_group": 1, "enemy_id": enemy.id, "role": "master"}]
    )

    run = await run_factory(state=RunState.CAMP, current_floor=1, next_group_id=group.id)
    camp = await camp_factory(
        run_id=run.id,
        spirit_id=spirit.id,
        candidate_a_item_id=candidate_a.id,
        candidate_b_item_id=candidate_b.id,
        floor=1,
        started_at=STARTED_AT,
        deadline_at=DEADLINE_AT,
    )

    ready_flags = ready_flags or [False] * member_count
    adventurers = []
    for i in range(member_count):
        adventurer = await adventurer_factory(run_id=run.id)
        await camp_member_factory(
            camp_id=camp.id,
            run_adventurer_id=adventurer.id,
            ready_at=STARTED_AT if ready_flags[i] else None,
        )
        adventurers.append(adventurer)

    return run, camp, adventurers


async def test_deadline_not_yet_reached_leaves_camp_open(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    enemy_factory,
    enemy_group_factory,
):
    run, camp, _adventurers = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        enemy_factory,
        enemy_group_factory,
    )

    just_before = DEADLINE_AT - timedelta(seconds=1)
    await ensure_camp_deadline_evaluated(
        db_session, run.id, now=just_before, random_source=random.Random(1)
    )

    await db_session.refresh(run)
    assert run.state == RunState.CAMP
    await db_session.refresh(camp)
    assert camp.ended_at is None


async def test_deadline_reached_exactly_forces_ready_and_ends_camp(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
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
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        enemy_factory,
        enemy_group_factory,
        ready_flags=[False, False],
    )

    await ensure_camp_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT, random_source=random.Random(1)
    )

    member_a = await get_camp_member(db_session, camp.id, a.id)
    member_b = await get_camp_member(db_session, camp.id, b.id)
    assert member_a.ready_at == DEADLINE_AT
    assert member_b.ready_at == DEADLINE_AT

    await db_session.refresh(run)
    assert run.state == RunState.BATTLE
    assert run.current_floor == 2

    events = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "adventurer_ready"
            )
        )
    ).scalars().all()
    assert {e.body["adventurer"] for e in events} == {str(a.id), str(b.id)}
    assert all(e.body["reason"] == "timeout" for e in events)

    camp_ended = (
        await db_session.execute(
            select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.event_type == "camp_ended")
        )
    ).scalar_one()
    assert camp_ended.body["reason"] == "timeout"


async def test_deadline_evaluation_does_not_force_ready_on_already_ready_members(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    enemy_factory,
    enemy_group_factory,
):
    run, camp, [a, _b] = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        enemy_factory,
        enemy_group_factory,
        ready_flags=[True, False],
    )

    await ensure_camp_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT, random_source=random.Random(1)
    )

    member_a = await get_camp_member(db_session, camp.id, a.id)
    assert member_a.ready_at == STARTED_AT  # untouched -- was already ready

    events = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "adventurer_ready"
            )
        )
    ).scalars().all()
    assert len(events) == 1  # only the not-yet-ready member gets a forced event


async def test_deadline_evaluation_is_idempotent_once_camp_has_ended(
    db_session,
    spell_factory,
    item_factory,
    spirit_factory,
    pool_entry_factory,
    run_factory,
    adventurer_factory,
    camp_factory,
    camp_member_factory,
    enemy_factory,
    enemy_group_factory,
):
    run, camp, _adventurers = await _setup_camp_with_members(
        spell_factory,
        item_factory,
        spirit_factory,
        pool_entry_factory,
        run_factory,
        adventurer_factory,
        camp_factory,
        camp_member_factory,
        enemy_factory,
        enemy_group_factory,
    )

    await ensure_camp_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT, random_source=random.Random(1)
    )
    await ensure_camp_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT + timedelta(hours=1), random_source=random.Random(1)
    )

    camp_ended_events = (
        await db_session.execute(
            select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.event_type == "camp_ended")
        )
    ).scalars().all()
    assert len(camp_ended_events) == 1


async def test_deadline_evaluation_is_a_no_op_when_run_is_not_in_camp(
    db_session, run_factory
):
    run = await run_factory(state=RunState.BATTLE, current_floor=1)

    result = await ensure_camp_deadline_evaluated(
        db_session, run.id, now=DEADLINE_AT, random_source=random.Random(1)
    )

    assert result.state == RunState.BATTLE
