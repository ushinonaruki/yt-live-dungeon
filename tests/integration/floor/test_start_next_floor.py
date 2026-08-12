from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from yt_live_dungeon.domain.errors import InvalidStatModifierError
from yt_live_dungeon.features.floor.start import start_next_floor
from yt_live_dungeon.persistence.models import RunEvent, RunState

NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def test_start_next_floor_heals_mp_to_item_inclusive_max(
    db_session, spell_factory, item_factory, run_factory, adventurer_factory, inventory_item_factory
):
    spell = await spell_factory()
    item = await item_factory(granted_spell_id=spell.id, base_stat_modifiers={"max_mp": 30})
    run = await run_factory(state=RunState.CAMP, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id, hp=100, mp=5)
    await inventory_item_factory(adventurer.id, item.id, slot=1, current_level=1)

    await start_next_floor(db_session, run, [adventurer], now=NOW)

    assert adventurer.mp == 100 + 30


async def test_start_next_floor_does_not_change_hp(
    db_session, run_factory, adventurer_factory
):
    run = await run_factory(state=RunState.CAMP, current_floor=1)
    adventurer = await adventurer_factory(run_id=run.id, hp=123, mp=10)

    await start_next_floor(db_session, run, [adventurer], now=NOW)

    assert adventurer.hp == 123


async def test_start_next_floor_increments_floor_and_sets_battle_state(
    db_session, run_factory, adventurer_factory
):
    run = await run_factory(state=RunState.CAMP, current_floor=3)
    adventurer = await adventurer_factory(run_id=run.id)

    await start_next_floor(db_session, run, [adventurer], now=NOW)

    assert run.current_floor == 4
    assert run.state == RunState.BATTLE


async def test_start_next_floor_only_touches_the_given_participants(
    db_session, run_factory, adventurer_factory
):
    run = await run_factory(state=RunState.CAMP, current_floor=1)
    participant = await adventurer_factory(run_id=run.id, hp=100, mp=1)
    bystander = await adventurer_factory(run_id=run.id, hp=100, mp=1, is_participating=False)

    await start_next_floor(db_session, run, [participant], now=NOW)

    assert participant.mp == 100  # healed to base_max_mp
    assert bystander.mp == 1  # untouched -- not in the participants list


async def test_start_next_floor_records_floor_started_event(
    db_session, run_factory, adventurer_factory
):
    run = await run_factory(state=RunState.CAMP, current_floor=5)
    adventurer = await adventurer_factory(run_id=run.id)

    await start_next_floor(db_session, run, [adventurer], now=NOW)

    event = (
        await db_session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run.id, RunEvent.event_type == "floor_started"
            )
        )
    ).scalar_one()
    assert event.body == {"floor": 6}


async def test_start_next_floor_raises_without_partial_update_on_invalid_item(
    db_session, spell_factory, item_factory, run_factory, adventurer_factory, inventory_item_factory
):
    spell = await spell_factory()
    broken_item = await item_factory(
        granted_spell_id=spell.id, base_stat_modifiers={"not_a_real_stat": 1}
    )
    run = await run_factory(state=RunState.CAMP, current_floor=2)
    adventurer = await adventurer_factory(run_id=run.id, hp=50, mp=5)
    await inventory_item_factory(adventurer.id, broken_item.id, slot=1, current_level=1)

    with pytest.raises(InvalidStatModifierError):
        await start_next_floor(db_session, run, [adventurer], now=NOW)

    # the floor/state fields this function would otherwise set are after
    # the per-participant recompute loop in source order, and nothing was
    # flushed/committed, so they remain exactly as before the call
    assert run.current_floor == 2
    assert run.state == RunState.CAMP
    assert adventurer.mp == 5
