import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run import Run


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
