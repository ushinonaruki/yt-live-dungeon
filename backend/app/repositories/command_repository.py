import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.command import Command


class CommandRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save(
        self,
        run_id: uuid.UUID,
        source: str,
        external_message_id: str,
        youtube_id: str,
        display_name: str,
        text: str,
        received_at: datetime,
    ) -> Command:
        command = Command(
            run_id=run_id,
            source=source,
            external_message_id=external_message_id,
            youtube_id=youtube_id,
            display_name=display_name,
            text=text,
            received_at=received_at,
        )
        self.db.add(command)
        await self.db.flush()
        return command
