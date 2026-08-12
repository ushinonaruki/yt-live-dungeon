import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome, HandlerRegistry, dispatch
from yt_live_dungeon.features.commands.parse import Unknown, parse
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.persistence.models import ProcessedCommand
from yt_live_dungeon.persistence.queries.processed_command import (
    find_by_source_and_message_id,
)
from yt_live_dungeon.persistence.queries.run import get_run_for_update


async def submit_command(
    session: AsyncSession,
    run_id: uuid.UUID,
    command_input: CommandInput,
    handlers: HandlerRegistry | None = None,
) -> ProcessedCommand:
    """Record a command idempotently and return its processed_commands row.

    The (source, source_message_id) key is reserved by flushing a
    provisional row *before* parsing or dispatching, so a concurrent
    duplicate blocks on the DB's own unique index instead of racing into a
    handler. Only that reserving flush() treats IntegrityError as "someone
    else already owns this command" -- any IntegrityError raised later, by
    a handler or by the final commit, propagates unchanged.

    `handlers` is supplied per call (never a module-global registry), so
    concurrent or unrelated submissions can never see each other's
    handlers or context.
    """
    existing = await find_by_source_and_message_id(
        session, command_input.source, command_input.source_message_id
    )
    if existing is not None:
        return existing

    # Lock the run row before creating the provisional record. The
    # provisional row's FK reference to runs.id already takes an implicit
    # FOR KEY SHARE lock on that row at INSERT time; if a handler (e.g.
    # @select) later takes its own FOR UPDATE on the same row, two
    # concurrent submissions for the same run can each hold the other's
    # required lock and deadlock. Acquiring FOR UPDATE here first fixes
    # the acquisition order for every command, not just the ones whose
    # handlers lock the run themselves.
    await get_run_for_update(session, run_id)

    provisional = ProcessedCommand(
        source=command_input.source,
        source_message_id=command_input.source_message_id,
        run_id=run_id,
        viewer_id=command_input.viewer_id,
        raw_text=command_input.raw_text,
        processed=False,
        reason=None,
        result=None,
        received_at=command_input.received_at,
        processed_at=None,
    )
    session.add(provisional)

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await find_by_source_and_message_id(
            session, command_input.source, command_input.source_message_id
        )
        if existing is None:
            raise
        return existing

    outcome = await _process(command_input, run_id, session, handlers or {})

    provisional.processed = outcome.processed
    provisional.reason = outcome.reason
    provisional.result = outcome.result
    provisional.processed_at = datetime.now(UTC)

    await session.commit()
    return provisional


async def _process(
    command_input: CommandInput,
    run_id: uuid.UUID,
    session: AsyncSession,
    handlers: HandlerRegistry,
) -> CommandOutcome:
    parsed = parse(command_input.raw_text)
    if isinstance(parsed, Unknown):
        return CommandOutcome(processed=False, reason=parsed.reason, result=None)

    context = CommandContext(session=session, run_id=run_id, command_input=command_input)
    return await dispatch(parsed, handlers, context)
