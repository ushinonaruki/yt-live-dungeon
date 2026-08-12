import pytest
from sqlalchemy.exc import IntegrityError


async def test_rejects_invalid_attribute(spell_factory):
    with pytest.raises(IntegrityError):
        await spell_factory(attribute="ZZ")


async def test_rejects_negative_mp_cost(spell_factory):
    with pytest.raises(IntegrityError):
        await spell_factory(mp_cost=-1)


async def test_rejects_empty_effects(spell_factory):
    with pytest.raises(IntegrityError):
        await spell_factory(effects=[])


async def test_accepts_valid_spell(spell_factory):
    spell = await spell_factory(mp_cost=0, effects=[{"type": "damage", "power": 1}])
    assert spell.id is not None
