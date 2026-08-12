import pytest
from sqlalchemy.exc import IntegrityError

from yt_live_dungeon.persistence.models import RunAdventurerItem


async def _setup_adventurer_with_two_items(
    spell_factory, item_factory, run_factory, adventurer_factory
):
    spell = await spell_factory()
    item_a = await item_factory(granted_spell_id=spell.id, item_key="item_a")
    item_b = await item_factory(granted_spell_id=spell.id, item_key="item_b")
    run = await run_factory()
    adventurer = await adventurer_factory(run_id=run.id)
    return adventurer, item_a, item_b


async def test_slot_must_be_within_1_to_8(
    db_session, spell_factory, item_factory, run_factory, adventurer_factory
):
    adventurer, item_a, _ = await _setup_adventurer_with_two_items(
        spell_factory, item_factory, run_factory, adventurer_factory
    )
    with pytest.raises(IntegrityError):
        db_session.add(
            RunAdventurerItem(
                run_adventurer_id=adventurer.id,
                item_id=item_a.id,
                slot=9,
                current_level=1,
                acquired_floor=1,
            )
        )
        await db_session.flush()


async def test_current_level_must_be_positive(
    db_session, spell_factory, item_factory, run_factory, adventurer_factory
):
    adventurer, item_a, _ = await _setup_adventurer_with_two_items(
        spell_factory, item_factory, run_factory, adventurer_factory
    )
    with pytest.raises(IntegrityError):
        db_session.add(
            RunAdventurerItem(
                run_adventurer_id=adventurer.id,
                item_id=item_a.id,
                slot=1,
                current_level=0,
                acquired_floor=1,
            )
        )
        await db_session.flush()


async def test_rejects_duplicate_slot_for_same_adventurer(
    db_session, spell_factory, item_factory, run_factory, adventurer_factory
):
    adventurer, item_a, item_b = await _setup_adventurer_with_two_items(
        spell_factory, item_factory, run_factory, adventurer_factory
    )
    db_session.add(
        RunAdventurerItem(
            run_adventurer_id=adventurer.id,
            item_id=item_a.id,
            slot=1,
            current_level=1,
            acquired_floor=1,
        )
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        db_session.add(
            RunAdventurerItem(
                run_adventurer_id=adventurer.id,
                item_id=item_b.id,
                slot=1,
                current_level=1,
                acquired_floor=1,
            )
        )
        await db_session.flush()


async def test_rejects_duplicate_item_for_same_adventurer(
    db_session, spell_factory, item_factory, run_factory, adventurer_factory
):
    adventurer, item_a, _ = await _setup_adventurer_with_two_items(
        spell_factory, item_factory, run_factory, adventurer_factory
    )
    db_session.add(
        RunAdventurerItem(
            run_adventurer_id=adventurer.id,
            item_id=item_a.id,
            slot=1,
            current_level=1,
            acquired_floor=1,
        )
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        db_session.add(
            RunAdventurerItem(
                run_adventurer_id=adventurer.id,
                item_id=item_a.id,
                slot=2,
                current_level=1,
                acquired_floor=1,
            )
        )
        await db_session.flush()
