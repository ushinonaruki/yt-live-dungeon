from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nickname_word import NicknameWord


class NicknameRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_all(self) -> list[NicknameWord]:
        result = await self.db.execute(select(NicknameWord))
        return list(result.scalars().all())
