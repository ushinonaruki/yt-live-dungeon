from sqlalchemy.ext.asyncio import AsyncSession

from app.core.command_parser import ParsedCommand, parse
from app.models.command import Command
from app.models.run import Run
from app.repositories.command_repository import CommandRepository
from app.repositories.log_repository import LogRepository
from app.repositories.pending_join_repository import PendingJoinRepository
from app.schemas.command import CommandEventIn


class CommandService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.command_repo = CommandRepository(db)
        self.log_repo = LogRepository(db)
        self.pending_join_repo = PendingJoinRepository(db)

    async def process(self, run: Run, event: CommandEventIn) -> dict:
        command = await self.command_repo.save(
            run_id=run.id,
            source=event.source,
            external_message_id=event.external_message_id,
            youtube_id=event.youtube_id,
            display_name=event.display_name,
            text=event.text,
            received_at=event.received_at,
        )

        parsed = parse(event.text)

        if parsed.type == "join":
            result = await self._handle_join(run, command, event, parsed)
        else:
            result = {"type": parsed.type, "processed": False}

        await self.db.commit()
        return result

    async def _handle_join(
        self,
        run: Run,
        command: Command,
        event: CommandEventIn,
        parsed: ParsedCommand,
    ) -> dict:
        oshi_name = parsed.target_name
        inserted = await self.pending_join_repo.add_if_not_exists(
            run_id=run.id,
            youtube_id=event.youtube_id,
            display_name=event.display_name,
            command_id=command.id,
            oshi_name=oshi_name,
        )
        event_type = "join_pending" if inserted else "join_duplicate"
        await self.log_repo.add(
            run_id=run.id,
            event_type=event_type,
            body={
                "youtube_id": event.youtube_id,
                "display_name": event.display_name,
                "oshi_name": oshi_name,
                "command_id": str(command.id),
            },
        )
        if inserted:
            return {"type": "join", "processed": True}
        return {"type": "join", "processed": False, "reason": "duplicate"}
