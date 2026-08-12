import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import RunEvent


async def list_events_after(
    session: AsyncSession, run_id: uuid.UUID, after: int
) -> list[RunEvent]:
    result = await session.execute(
        select(RunEvent)
        .where(RunEvent.run_id == run_id, RunEvent.sequence > after)
        .order_by(RunEvent.sequence.asc())
    )
    return list(result.scalars().all())


async def append_event(
    session: AsyncSession, run_id: uuid.UUID, event_type: str, body: dict
) -> RunEvent:
    """Add a new RunEvent with the next sequence number for `run_id`.

    Callers must already hold the run row's SELECT ... FOR UPDATE lock
    within the current transaction -- that lock, not this query, is what
    serializes concurrent sequence allocation for the same run.
    """
    result = await session.execute(
        select(func.coalesce(func.max(RunEvent.sequence), 0)).where(RunEvent.run_id == run_id)
    )
    next_sequence = result.scalar_one() + 1

    event = RunEvent(run_id=run_id, sequence=next_sequence, event_type=event_type, body=body)
    session.add(event)
    return event
