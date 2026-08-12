from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from yt_live_dungeon.features.commands.parse import ParsedCommand

NOT_IMPLEMENTED = "not_implemented"


@dataclass(frozen=True)
class CommandOutcome:
    processed: bool
    reason: str | None
    result: dict | None


# `context` is opaque to the dispatcher (typically a CommandContext built by
# the caller); handlers must not commit or roll back whatever session it
# carries -- that stays the caller's responsibility.
CommandHandler = Callable[[ParsedCommand, Any], Awaitable[CommandOutcome]]
HandlerRegistry = Mapping[type, CommandHandler]


async def dispatch(
    command: ParsedCommand, handlers: HandlerRegistry, context: Any
) -> CommandOutcome:
    handler = handlers.get(type(command))
    if handler is None:
        return CommandOutcome(processed=False, reason=NOT_IMPLEMENTED, result=None)
    return await handler(command, context)
