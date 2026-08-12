import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import RunAdventurer, RunCamp, RunCampMember


async def get_camp_by_run_and_floor(
    session: AsyncSession, run_id: uuid.UUID, floor: int
) -> RunCamp | None:
    result = await session.execute(
        select(RunCamp).where(RunCamp.run_id == run_id, RunCamp.floor == floor)
    )
    return result.scalar_one_or_none()


async def get_open_camp(session: AsyncSession, run_id: uuid.UUID, floor: int) -> RunCamp | None:
    result = await session.execute(
        select(RunCamp).where(
            RunCamp.run_id == run_id,
            RunCamp.floor == floor,
            RunCamp.ended_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_camp_member(
    session: AsyncSession, camp_id: uuid.UUID, run_adventurer_id: uuid.UUID
) -> RunCampMember | None:
    return await session.get(RunCampMember, (camp_id, run_adventurer_id))


async def list_camp_members(
    session: AsyncSession, camp_id: uuid.UUID
) -> list[tuple[RunCampMember, RunAdventurer]]:
    """(RunCampMember, RunAdventurer) pairs for a camp, in a deterministic
    (adventurer join order) order."""
    result = await session.execute(
        select(RunCampMember, RunAdventurer)
        .join(RunAdventurer, RunAdventurer.id == RunCampMember.run_adventurer_id)
        .where(RunCampMember.camp_id == camp_id)
        .order_by(RunAdventurer.created_at, RunAdventurer.id)
    )
    return list(result.all())
