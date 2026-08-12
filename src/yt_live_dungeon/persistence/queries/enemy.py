from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import Enemy, EnemySpell, Spell


async def get_enemy(session: AsyncSession, enemy_id: int) -> Enemy | None:
    return await session.get(Enemy, enemy_id)


async def list_enemy_spells(session: AsyncSession, enemy_id: int) -> list[Spell]:
    """Active Spells usable by one Enemy template, ordered by id for a
    deterministic candidate list."""
    result = await session.execute(
        select(Spell)
        .join(EnemySpell, EnemySpell.spell_id == Spell.id)
        .where(EnemySpell.enemy_id == enemy_id, Spell.is_active.is_(True))
        .order_by(Spell.id)
    )
    return list(result.scalars().all())
