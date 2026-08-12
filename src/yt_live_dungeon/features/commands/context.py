import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.features.commands.types import CommandInput


@dataclass(frozen=True)
class CommandContext:
    """Per-call execution context passed to command handlers.

    Built fresh by submit_command() for each call; never shared or reused
    across requests. Handlers must not commit or roll back `session` --
    submit_command() owns the single transaction boundary.
    """

    session: AsyncSession
    run_id: uuid.UUID
    command_input: CommandInput
