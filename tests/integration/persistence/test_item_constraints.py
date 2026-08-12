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
