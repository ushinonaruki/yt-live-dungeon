import pytest
from sqlalchemy.exc import IntegrityError

from yt_live_dungeon.persistence.models import EnemyGroup, EnemyGroupMember


async def _make_group(db_session, **overrides):
    defaults = dict(group_key="test_group", display_name="test group", is_active=True)
    defaults.update(overrides)
    group = EnemyGroup(**defaults)
    db_session.add(group)
    await db_session.flush()
    return group


async def test_rejects_invalid_role(db_session, enemy_factory):
    enemy = await enemy_factory()
    group = await _make_group(db_session)

    with pytest.raises(IntegrityError):
        db_session.add(
            EnemyGroupMember(group_id=group.id, order_in_group=1, enemy_id=enemy.id, role="boss")
        )
        await db_session.flush()


async def test_rejects_order_in_group_above_nine(db_session, enemy_factory):
    enemy = await enemy_factory()
    group = await _make_group(db_session)

    with pytest.raises(IntegrityError):
        db_session.add(
            EnemyGroupMember(
                group_id=group.id, order_in_group=10, enemy_id=enemy.id, role="minion"
            )
        )
        await db_session.flush()


async def test_rejects_order_in_group_below_one(db_session, enemy_factory):
    enemy = await enemy_factory()
    group = await _make_group(db_session)

    with pytest.raises(IntegrityError):
        db_session.add(
            EnemyGroupMember(group_id=group.id, order_in_group=0, enemy_id=enemy.id, role="master")
        )
        await db_session.flush()


async def test_rejects_duplicate_order_in_group_for_same_group(db_session, enemy_factory):
    enemy_a = await enemy_factory(enemy_key="enemy_a")
    enemy_b = await enemy_factory(enemy_key="enemy_b")
    group = await _make_group(db_session)
    db_session.add(
        EnemyGroupMember(group_id=group.id, order_in_group=1, enemy_id=enemy_a.id, role="master")
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        db_session.add(
            EnemyGroupMember(
                group_id=group.id, order_in_group=1, enemy_id=enemy_b.id, role="minion"
            )
        )
        await db_session.flush()


async def test_rejects_a_second_master_in_the_same_group(db_session, enemy_factory):
    enemy_a = await enemy_factory(enemy_key="enemy_a")
    enemy_b = await enemy_factory(enemy_key="enemy_b")
    group = await _make_group(db_session)
    db_session.add(
        EnemyGroupMember(group_id=group.id, order_in_group=1, enemy_id=enemy_a.id, role="master")
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        db_session.add(
            EnemyGroupMember(
                group_id=group.id, order_in_group=2, enemy_id=enemy_b.id, role="master"
            )
        )
        await db_session.flush()


async def test_allows_two_different_groups_to_each_have_their_own_master(db_session, enemy_factory):
    enemy_a = await enemy_factory(enemy_key="enemy_a")
    enemy_b = await enemy_factory(enemy_key="enemy_b")
    group_a = await _make_group(db_session, group_key="group_a")
    group_b = await _make_group(db_session, group_key="group_b")

    db_session.add(
        EnemyGroupMember(group_id=group_a.id, order_in_group=1, enemy_id=enemy_a.id, role="master")
    )
    db_session.add(
        EnemyGroupMember(group_id=group_b.id, order_in_group=1, enemy_id=enemy_b.id, role="master")
    )
    await db_session.flush()  # no IntegrityError -- one master per *group*, not globally
