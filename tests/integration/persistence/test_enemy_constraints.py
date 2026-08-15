import pytest
from sqlalchemy.exc import IntegrityError

from yt_live_dungeon.persistence.models import Enemy


async def test_accepts_base_max_mp_of_100(enemy_factory):
    enemy = await enemy_factory(base_max_mp=100)
    assert enemy.id is not None


async def test_rejects_base_max_mp_other_than_100(db_session, enemy_factory):
    """Per obsidian/.../キャラクター/ステータス.md section 5: max MP is
    fixed at 100 for every combatant, never varied per enemy template."""
    with pytest.raises(IntegrityError):
        db_session.add(
            Enemy(
                enemy_key="test_enemy_bad_mp",
                display_name="test enemy",
                base_max_hp=100,
                base_max_mp=20,
                base_attributes={},
                break_max=50,
            )
        )
        await db_session.flush()
