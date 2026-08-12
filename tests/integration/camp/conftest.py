import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from yt_live_dungeon.domain.attributes import ATTRIBUTE_MODIFIER_KEYS
from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Enemy,
    EnemyGroup,
    EnemyGroupMember,
    Item,
    Run,
    RunAdventurer,
    RunAdventurerItem,
    RunCamp,
    RunCampMember,
    RunState,
    Spell,
    Spirit,
    SpiritItemPoolEntry,
)


def unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def spell_factory(db_session):
    async def _create(**overrides) -> Spell:
        defaults = dict(
            command=unique("spell"),
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
            item_key=unique("item"),
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
def spirit_factory(db_session):
    async def _create(blessing_item_id: int, **overrides) -> Spirit:
        defaults = dict(
            spirit_key=unique("spirit"),
            display_name="test spirit",
            representative_attribute="RR",
            blessing_item_id=blessing_item_id,
            is_active=True,
        )
        defaults.update(overrides)
        spirit = Spirit(**defaults)
        db_session.add(spirit)
        await db_session.flush()
        return spirit

    return _create


@pytest.fixture
def pool_entry_factory(db_session):
    async def _create(spirit_id: int, item_id: int) -> SpiritItemPoolEntry:
        entry = SpiritItemPoolEntry(spirit_id=spirit_id, item_id=item_id)
        db_session.add(entry)
        await db_session.flush()
        return entry

    return _create


@pytest.fixture
def run_factory(db_session):
    async def _create(**overrides) -> Run:
        defaults = dict(state=RunState.BATTLE, current_floor=1)
        defaults.update(overrides)
        run = Run(**defaults)
        db_session.add(run)
        await db_session.flush()
        return run

    return _create


@pytest.fixture
def adventurer_factory(db_session):
    async def _create(run_id: uuid.UUID, **overrides) -> RunAdventurer:
        defaults = dict(
            run_id=run_id,
            youtube_id=unique("viewer"),
            hp=500,
            mp=100,
            base_max_hp=500,
            base_max_mp=100,
            is_alive=True,
            is_participating=True,
        )
        defaults.update(overrides)
        adventurer = RunAdventurer(**defaults)
        db_session.add(adventurer)
        await db_session.flush()
        return adventurer

    return _create


@pytest.fixture
def inventory_item_factory(db_session):
    async def _create(
        run_adventurer_id: uuid.UUID, item_id: int, **overrides
    ) -> RunAdventurerItem:
        defaults = dict(
            run_adventurer_id=run_adventurer_id,
            item_id=item_id,
            slot=1,
            current_level=1,
            acquired_floor=1,
        )
        defaults.update(overrides)
        row = RunAdventurerItem(**defaults)
        db_session.add(row)
        await db_session.flush()
        return row

    return _create


@pytest.fixture
def camp_factory(db_session):
    async def _create(
        run_id: uuid.UUID,
        spirit_id: int,
        candidate_a_item_id: int,
        candidate_b_item_id: int,
        **overrides,
    ) -> RunCamp:
        started_at = datetime.now(UTC)
        defaults = dict(
            run_id=run_id,
            floor=1,
            spirit_id=spirit_id,
            candidate_a_item_id=candidate_a_item_id,
            candidate_b_item_id=candidate_b_item_id,
            started_at=started_at,
            deadline_at=started_at + timedelta(minutes=5),
            ended_at=None,
        )
        defaults.update(overrides)
        camp = RunCamp(**defaults)
        db_session.add(camp)
        await db_session.flush()
        return camp

    return _create


@pytest.fixture
def camp_member_factory(db_session):
    async def _create(
        camp_id: uuid.UUID, run_adventurer_id: uuid.UUID, **overrides
    ) -> RunCampMember:
        defaults = dict(
            camp_id=camp_id,
            run_adventurer_id=run_adventurer_id,
            can_select_action=True,
            selected_action=None,
            selected_at=None,
            ready_at=None,
            left_at=None,
        )
        defaults.update(overrides)
        member = RunCampMember(**defaults)
        db_session.add(member)
        await db_session.flush()
        return member

    return _create


@pytest.fixture
def enemy_factory(db_session):
    async def _create(**overrides) -> Enemy:
        defaults = dict(
            enemy_key=unique("enemy"),
            display_name="test enemy",
            base_max_hp=100,
            base_max_mp=20,
            base_attributes=dict.fromkeys(ATTRIBUTE_MODIFIER_KEYS, 5),
            weak_attribute=None,
            break_max=50,
            ai_policy_key="random_v1",
            ai_policy_config={},
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
        defaults = dict(group_key=unique("group"), display_name="test group", is_active=True)
        defaults.update(overrides)
        group = EnemyGroup(**defaults)
        db_session.add(group)
        await db_session.flush()
        for member in members:
            db_session.add(EnemyGroupMember(group_id=group.id, **member))
        await db_session.flush()
        return group

    return _create
