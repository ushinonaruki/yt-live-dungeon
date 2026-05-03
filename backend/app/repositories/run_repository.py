import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run import Run, RunState


class RunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self) -> Run:
        run = Run()
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def get(self, run_id: uuid.UUID) -> Run | None:
        result = await self.db.execute(select(Run).where(Run.id == run_id))
        return result.scalar_one_or_none()

    async def begin_floor(self, run: Run, new_floor: int) -> None:
        if run.started_at is None:
            run.started_at = datetime.now(timezone.utc)
        run.current_floor = new_floor
        run.state = RunState.BATTLE
        await self.db.flush()
