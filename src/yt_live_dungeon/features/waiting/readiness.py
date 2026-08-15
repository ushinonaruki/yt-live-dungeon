import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.queries.adventurer import list_active_participants


async def all_active_participants_ready(session: AsyncSession, run_id: uuid.UUID) -> bool:
    """True if every currently alive & participating adventurer has
    waiting_ready_at set. Vacuously true when there are no active
    participants at all (callers that need to treat "zero participants"
    as a distinct case check that separately).

    Mirrors features/camp/readiness.py's all_active_participants_ready,
    but reads RunAdventurer.waiting_ready_at directly instead of joining
    a per-floor RunCampMember row -- WAITING happens at most once per
    run and has no RunCamp to attach a membership row to.
    """
    participants = await list_active_participants(session, run_id)
    if not participants:
        return True
    return all(p.waiting_ready_at is not None for p in participants)
