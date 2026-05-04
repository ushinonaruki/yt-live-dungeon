import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.command_parser import ParsedCommand, parse
from app.core.cooldown import is_on_cooldown, set_cooldown
from app.models.command import Command
from app.models.run import Run, RunState
from app.repositories.adventurer_repository import AdventurerRepository
from app.repositories.command_repository import CommandRepository
from app.repositories.log_repository import LogRepository
from app.repositories.pending_join_repository import PendingJoinRepository
from app.schemas.command import CommandEventIn, CommandResult
from app.services.battle_service import BattleService, NoAliveEnemyError

_HINOKINOFUTA_COOLDOWN_SECONDS = 20


class CommandService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis
        self.command_repo = CommandRepository(db)
        self.log_repo = LogRepository(db)
        self.pending_join_repo = PendingJoinRepository(db)
        self.adventurer_repo = AdventurerRepository(db)
        self.battle_service = BattleService(db)

    async def process(self, run: Run, event: CommandEventIn) -> CommandResult:
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
        elif parsed.type == "spell":
            result = await self._handle_spell(run, command, event, parsed)
        else:
            result = CommandResult(type=parsed.type, processed=False)

        await self.db.commit()
        return result

    async def _handle_join(
        self,
        run: Run,
        command: Command,
        event: CommandEventIn,
        parsed: ParsedCommand,
    ) -> CommandResult:
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
            return CommandResult(type="join", processed=True)
        return CommandResult(type="join", processed=False, reason="duplicate")

    async def _handle_spell(
        self,
        run: Run,
        command: Command,
        event: CommandEventIn,
        parsed: ParsedCommand,
    ) -> CommandResult:
        match parsed.spell_name:
            case "hinokinofuta":
                if parsed.target_name is not None:
                    return CommandResult(
                        type="spell", processed=False, reason="invalid_target"
                    )
                return await self._handle_hinokinofuta(run, event)
            case _:
                return CommandResult(
                    type="spell", processed=False, reason="unknown_spell"
                )

    async def _handle_hinokinofuta(
        self,
        run: Run,
        event: CommandEventIn,
    ) -> CommandResult:
        if run.state != RunState.BATTLE:
            return CommandResult(type="spell", processed=False, reason="not_in_battle")

        adventurer = await self.adventurer_repo.get_alive_by_youtube_id(
            run.id, event.youtube_id
        )
        if adventurer is None:
            return CommandResult(type="spell", processed=False, reason="not_joined")

        has_item = await self.adventurer_repo.has_item_unlocking_spell(
            adventurer.id, "hinokinofuta"
        )
        if not has_item:
            return CommandResult(
                type="spell", processed=False, reason="spell_not_unlocked"
            )

        if await is_on_cooldown(self.redis, adventurer.id):
            return CommandResult(type="spell", processed=False, reason="on_cooldown")

        try:
            await self.battle_service.use_hinokinofuta(run=run, adventurer=adventurer)
        except NoAliveEnemyError:
            # spell_no_target ログは BattleService 側で出力済み
            return CommandResult(type="spell", processed=False, reason="no_alive_enemy")

        await set_cooldown(
            self.redis, adventurer.id, "hinokinofuta", _HINOKINOFUTA_COOLDOWN_SECONDS
        )
        return CommandResult(type="spell", processed=True)
