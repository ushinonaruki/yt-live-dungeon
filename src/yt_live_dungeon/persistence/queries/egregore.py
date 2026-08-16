from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import Egregore, EgregoreItemPoolEntry, Item


async def get_egregore(session: AsyncSession, egregore_id: int) -> Egregore | None:
    return await session.get(Egregore, egregore_id)


async def list_active_egregore_ids(session: AsyncSession) -> list[int]:
    """Active egregore ids, ordered by id for a deterministic draw
    population (see list_active_pool_item_ids for why the ORDER BY
    matters for a seeded RandomSource.sample())."""
    result = await session.execute(
        select(Egregore.id).where(Egregore.is_active.is_(True)).order_by(Egregore.id)
    )
    return list(result.scalars().all())


async def list_active_pool_item_ids(session: AsyncSession, egregore_id: int) -> list[int]:
    """Active pool item ids for one egregore, ordered by item_id.

    The explicit ORDER BY matters beyond readability: callers pass this
    list to a seeded RandomSource.sample() and rely on the draw being
    reproducible from the seed alone, not on whatever row order Postgres
    happens to return.
    """
    result = await session.execute(
        select(EgregoreItemPoolEntry.item_id)
        .join(Item, Item.id == EgregoreItemPoolEntry.item_id)
        .where(EgregoreItemPoolEntry.egregore_id == egregore_id, Item.is_active.is_(True))
        .order_by(EgregoreItemPoolEntry.item_id)
    )
    return list(result.scalars().all())
