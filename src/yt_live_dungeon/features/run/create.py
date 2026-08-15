from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.models import Run, RunState
from yt_live_dungeon.persistence.queries.event import append_event


async def create_run(session: AsyncSession) -> Run:
    """Creates a brand-new run in WAITING, ready for initial participation.

    waiting_deadline_at is left unset: per obsidian/.../進行/参加受付.md
    section 3, the initial-participation deadline never starts at run
    creation -- it starts only once the first successful @login sets it
    (see features/waiting/login.py). No enemy group or RunEnemy is
    drawn/spawned here; that happens only once start_run() runs, at 1F
    start.

    Never commits -- the caller owns the transaction.
    """
    run = Run(state=RunState.WAITING, waiting_deadline_at=None)
    session.add(run)
    await session.flush()

    await append_event(session, run.id, "run_created", {})

    return run
