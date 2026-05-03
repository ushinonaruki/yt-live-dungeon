import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import Log


class LogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, run_id: uuid.UUID, event_type: str, body: dict) -> Log:
        log = Log(run_id=run_id, event_type=event_type, body=body)
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_by_run(
        self, run_id: uuid.UUID, since: int | None = None
    ) -> list[Log]:
        q = select(Log).where(Log.run_id == run_id)
        if since is not None:
            q = q.where(Log.id > since)
        q = q.order_by(Log.id)
        result = await self.db.execute(q)
        return list(result.scalars().all())
