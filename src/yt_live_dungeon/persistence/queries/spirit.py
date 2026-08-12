from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import Item, Spirit, SpiritItemPoolEntry


async def get_spirit(session: AsyncSession, spirit_id: int) -> Spirit | None:
    return await session.get(Spirit, spirit_id)


async def list_active_pool_item_ids(session: AsyncSession, spirit_id: int) -> list[int]:
    """Active pool item ids for one spirit, ordered by item_id.

    The explicit ORDER BY matters beyond readability: callers pass this
    list to a seeded RandomSource.sample() and rely on the draw being
    reproducible from the seed alone, not on whatever row order Postgres
    happens to return.
    """
    result = await session.execute(
        select(SpiritItemPoolEntry.item_id)
        .join(Item, Item.id == SpiritItemPoolEntry.item_id)
        .where(SpiritItemPoolEntry.spirit_id == spirit_id, Item.is_active.is_(True))
        .order_by(SpiritItemPoolEntry.item_id)
    )
    return list(result.scalars().all())
