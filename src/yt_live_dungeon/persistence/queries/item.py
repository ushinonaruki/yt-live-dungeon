from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import Item


async def get_item(session: AsyncSession, item_id: int) -> Item | None:
    return await session.get(Item, item_id)
