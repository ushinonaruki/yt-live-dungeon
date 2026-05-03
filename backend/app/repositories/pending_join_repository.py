import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run_pending_join import RunPendingJoin


class PendingJoinRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add_if_not_exists(
        self,
        run_id: uuid.UUID,
        youtube_id: str,
        display_name: str,
        command_id: uuid.UUID,
    ) -> bool:
        """INSERT ON CONFLICT DO NOTHING。挿入できた場合 True、重複だった場合 False を返す。"""
        stmt = (
            pg_insert(RunPendingJoin)
            .values(
                id=uuid.uuid4(),
                run_id=run_id,
                youtube_id=youtube_id,
                display_name=display_name,
                command_id=command_id,
            )
            .on_conflict_do_nothing(constraint="uq_pending_join")
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def list_by_run(self, run_id: uuid.UUID) -> list[RunPendingJoin]:
        result = await self.db.execute(
            select(RunPendingJoin)
            .where(RunPendingJoin.run_id == run_id)
            .order_by(RunPendingJoin.created_at)
        )
        return list(result.scalars().all())
