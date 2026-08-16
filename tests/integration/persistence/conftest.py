import pytest
import pytest_asyncio

from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Egregore,
    Enemy,
    EnemyGroup,
    EnemyGroupMember,
    Item,
    Run,
    RunAdventurer,
    Spell,
)


@pytest_asyncio.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def spell_factory(db_session):
    async def _create(**overrides) -> Spell:
        defaults = dict(
            command="test_spell",
            display_name="test spell",
            attribute="RR",
            mp_cost=0,
            target_rule="single_enemy",
            effects=[{"type": "damage", "power": 1}],
            is_active=True,
        )
        defaults.update(overrides)
        spell = Spell(**defaults)
        db_session.add(spell)
        await db_session.flush()
        return spell

    return _create


@pytest.fixture
def item_factory(db_session):
    async def _create(granted_spell_id: int, **overrides) -> Item:
        defaults = dict(
            item_key="test_item",
            display_name="test item",
            attribute="RR",
            granted_spell_id=granted_spell_id,
            base_stat_modifiers={},
            per_level_stat_modifiers={},
            break_effects=[],
            is_active=True,
        )
        defaults.update(overrides)
        item = Item(**defaults)
        db_session.add(item)
        await db_session.flush()
        return item

    return _create


@pytest.fixture
def egregore_factory(db_session):
    async def _create(blessing_item_id: int, **overrides) -> Egregore:
        defaults = dict(
            egregore_key="test_egregore",
            display_name="test egregore",
            representative_attribute="RR",
            blessing_item_id=blessing_item_id,
            is_active=True,
        )
        defaults.update(overrides)
        egregore = Egregore(**defaults)
        db_session.add(egregore)
        await db_session.flush()
        return egregore

    return _create


@pytest.fixture
def run_factory(db_session):
    async def _create(**overrides) -> Run:
        run = Run(**overrides)
        db_session.add(run)
        await db_session.flush()
        return run

    return _create


@pytest.fixture
def adventurer_factory(db_session):
    async def _create(run_id, **overrides) -> RunAdventurer:
        defaults = dict(
            run_id=run_id,
            youtube_id="test_viewer",
            hp=500,
            mp=100,
        )
        defaults.update(overrides)
        adventurer = RunAdventurer(**defaults)
        db_session.add(adventurer)
        await db_session.flush()
        return adventurer

    return _create


@pytest.fixture
def enemy_factory(db_session):
    async def _create(**overrides) -> Enemy:
        defaults = dict(
            enemy_key="test_enemy",
            display_name="test enemy",
            base_max_hp=100,
            base_max_mp=100,
            base_attributes={},
            break_max=50,
            is_active=True,
        )
        defaults.update(overrides)
        enemy = Enemy(**defaults)
        db_session.add(enemy)
        await db_session.flush()
        return enemy

    return _create


@pytest.fixture
def enemy_group_factory(db_session):
    async def _create(members: list[dict], **overrides) -> EnemyGroup:
        defaults = dict(group_key="test_group", display_name="test group", is_active=True)
        defaults.update(overrides)
        group = EnemyGroup(**defaults)
        db_session.add(group)
        await db_session.flush()
        for member in members:
            db_session.add(EnemyGroupMember(group_id=group.id, **member))
        await db_session.flush()
        return group

    return _create
