import pytest
from sqlalchemy.exc import IntegrityError


async def test_rejects_invalid_attribute(spell_factory, item_factory):
    spell = await spell_factory()
    with pytest.raises(IntegrityError):
        await item_factory(granted_spell_id=spell.id, attribute="ZZ")


async def test_requires_granted_spell(item_factory):
    with pytest.raises(IntegrityError):
        await item_factory(granted_spell_id=None)


async def test_accepts_valid_item(spell_factory, item_factory):
    spell = await spell_factory()
    item = await item_factory(granted_spell_id=spell.id)
    assert item.id is not None


async def test_rejects_max_mp_in_base_stat_modifiers(spell_factory, item_factory):
    """Per obsidian/.../アイテム/アイテム定義仕様.md section 7: max MP is
    fixed at 100 for every combatant, so an item may never carry a
    "max_mp" stat modifier."""
    spell = await spell_factory()
    with pytest.raises(IntegrityError):
        await item_factory(granted_spell_id=spell.id, base_stat_modifiers={"max_mp": 10})


async def test_rejects_max_mp_in_per_level_stat_modifiers(spell_factory, item_factory):
    spell = await spell_factory()
    with pytest.raises(IntegrityError):
        await item_factory(granted_spell_id=spell.id, per_level_stat_modifiers={"max_mp": 1})
