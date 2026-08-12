from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import Spell


async def get_spell(session: AsyncSession, spell_id: int) -> Spell | None:
    return await session.get(Spell, spell_id)


async def get_active_spell_by_command(session: AsyncSession, command: str) -> Spell | None:
    result = await session.execute(
        select(Spell).where(Spell.command == command, Spell.is_active.is_(True))
    )
    return result.scalar_one_or_none()
