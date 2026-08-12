import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.queries.adventurer import list_active_participants
from yt_live_dungeon.persistence.queries.camp import list_camp_members


async def all_active_participants_ready(
    session: AsyncSession, run_id: uuid.UUID, camp_id: uuid.UUID
) -> bool:
    """True if every currently alive & participating adventurer has a
    ready_at set on their membership for `camp_id`. Vacuously true when
    there are no active participants at all (callers that need to treat
    "zero participants" as a distinct case check that separately)."""
    participants = await list_active_participants(session, run_id)
    if not participants:
        return True

    members = await list_camp_members(session, camp_id)
    ready_by_adventurer_id = {
        member.run_adventurer_id: member.ready_at is not None for member, _adventurer in members
    }
    return all(ready_by_adventurer_id.get(p.id, False) for p in participants)
