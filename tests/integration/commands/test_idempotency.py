import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Ready
from yt_live_dungeon.features.commands.submit import submit_command
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import ProcessedCommand, Run


async def _create_run() -> Run:
    async with async_session_factory() as session:
        run = Run()
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


def _unique_message_id(label: str) -> str:
    # Unique per invocation so repeated test runs against a not-freshly-reset
    # database never collide with a previously committed row of the same key.
    return f"{label}-{uuid.uuid4().hex}"


def _command_input(**overrides) -> CommandInput:
    defaults = dict(
        source="youtube_live",
        source_message_id=_unique_message_id("command"),
        viewer_id="viewer-1",
        viewer_display_name="Viewer One",
        raw_text="@ready",
        received_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return CommandInput(**defaults)


async def _row_count(source: str, source_message_id: str) -> int:
    async with async_session_factory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(ProcessedCommand)
            .where(
                ProcessedCommand.source == source,
                ProcessedCommand.source_message_id == source_message_id,
            )
        )
        return result.scalar_one()


def _recording_handler():
    calls: list[CommandContext] = []

    async def handler(command, context: CommandContext) -> CommandOutcome:
        calls.append(context)
        return CommandOutcome(processed=True, reason=None, result={"handled": True})

    return handler, calls


async def test_first_submission_is_processed_once():
    run = await _create_run()
    command_input = _command_input(source_message_id=_unique_message_id("first-only"))

    async with async_session_factory() as session:
        record = await submit_command(session, run.id, command_input)

    assert record.reason == "not_implemented"
    assert record.processed_at is not None
    assert await _row_count("youtube_live", command_input.source_message_id) == 1


async def test_resubmission_returns_the_same_result_without_reprocessing():
    run = await _create_run()
    command_input = _command_input(source_message_id=_unique_message_id("resubmitted"))

    async with async_session_factory() as session:
        first = await submit_command(session, run.id, command_input)

    async with async_session_factory() as session:
        second = await submit_command(session, run.id, command_input)

    assert first.id == second.id
    assert first.processed == second.processed
    assert first.reason == second.reason
    assert first.result == second.result
    assert await _row_count("youtube_live", command_input.source_message_id) == 1


async def test_resubmission_does_not_invoke_handler_again():
    run = await _create_run()
    command_input = _command_input(
        source_message_id=_unique_message_id("no-recall"), raw_text="@ready"
    )
    handler, calls = _recording_handler()
    handlers = {Ready: handler}

    async with async_session_factory() as session:
        first = await submit_command(session, run.id, command_input, handlers=handlers)

    async with async_session_factory() as session:
        second = await submit_command(session, run.id, command_input, handlers=handlers)

    assert len(calls) == 1
    assert first.id == second.id
    assert second.result == {"handled": True}


async def test_concurrent_duplicate_submissions_do_not_raise_and_leave_one_row():
    run = await _create_run()
    command_input = _command_input(source_message_id=_unique_message_id("race-message"))

    async def _submit() -> ProcessedCommand:
        async with async_session_factory() as session:
            return await submit_command(session, run.id, command_input)

    first, second = await asyncio.gather(_submit(), _submit())

    assert first.id == second.id
    assert await _row_count("youtube_live", command_input.source_message_id) == 1


async def test_concurrent_duplicate_submissions_call_handler_exactly_once():
    run = await _create_run()
    command_input = _command_input(
        source_message_id=_unique_message_id("race-message-handler"), raw_text="@ready"
    )

    # Each concurrent _submit() builds its own handler closed over its own
    # `session`, so a handler invocation can only report `context.session is
    # session` truthfully if it actually received *that* call's session --
    # not merely a non-null session from either call.
    invocations: list[dict] = []

    async def _submit() -> ProcessedCommand:
        async with async_session_factory() as session:

            async def handler(command, context: CommandContext) -> CommandOutcome:
                invocations.append(
                    {"context": context, "session_is_own_session": context.session is session}
                )
                return CommandOutcome(processed=True, reason=None, result={"handled": True})

            return await submit_command(
                session, run.id, command_input, handlers={Ready: handler}
            )

    first, second = await asyncio.gather(_submit(), _submit())

    # exactly one handler invocation across both concurrent requests
    assert len(invocations) == 1
    invocation = invocations[0]
    assert invocation["session_is_own_session"] is True

    context = invocation["context"]
    assert context.run_id == run.id
    assert context.command_input == command_input

    # both requests observe the same, fully persisted winning result
    assert first.id == second.id
    assert first.processed is True
    assert first.reason is None
    assert first.result == {"handled": True}
    assert second.processed is True
    assert second.reason is None
    assert second.result == {"handled": True}

    assert await _row_count("youtube_live", command_input.source_message_id) == 1


async def test_context_is_isolated_between_separate_submissions():
    run = await _create_run()

    command_input_a = _command_input(
        source_message_id=_unique_message_id("isolated-a"), raw_text="@ready"
    )
    command_input_b = _command_input(
        source_message_id=_unique_message_id("isolated-b"), raw_text="@ready"
    )

    captured_a: list[CommandContext] = []
    captured_b: list[CommandContext] = []

    async with async_session_factory() as session_a:

        async def handler_a(command, context: CommandContext) -> CommandOutcome:
            captured_a.append(context)
            return CommandOutcome(processed=True, reason=None, result={"call": "a"})

        await submit_command(session_a, run.id, command_input_a, handlers={Ready: handler_a})

    async with async_session_factory() as session_b:

        async def handler_b(command, context: CommandContext) -> CommandOutcome:
            captured_b.append(context)
            return CommandOutcome(processed=True, reason=None, result={"call": "b"})

        await submit_command(session_b, run.id, command_input_b, handlers={Ready: handler_b})

    assert len(captured_a) == 1
    assert len(captured_b) == 1

    context_a = captured_a[0]
    context_b = captured_b[0]

    # separate CommandContext instances, each carrying its own call's
    # exact session and command_input -- neither leaked into the other
    assert context_a is not context_b
    assert context_a.command_input == command_input_a
    assert context_b.command_input == command_input_b
    assert context_a.session is session_a
    assert context_b.session is session_b
    assert context_a.session is not context_b.session


async def test_handlers_do_not_leak_between_unrelated_submissions():
    run = await _create_run()
    handler, calls = _recording_handler()
    handlers = {Ready: handler}

    async with async_session_factory() as session:
        await submit_command(
            session,
            run.id,
            _command_input(source_message_id=_unique_message_id("leak-1"), raw_text="@ready"),
            handlers=handlers,
        )

    # A separate submission for a different command, with no handlers
    # supplied, must fall back to not_implemented -- it must not see the
    # handler registered for the earlier call.
    async with async_session_factory() as session:
        second = await submit_command(
            session,
            run.id,
            _command_input(source_message_id=_unique_message_id("leak-2"), raw_text="@ready"),
        )

    assert len(calls) == 1
    assert second.processed is False
    assert second.reason == "not_implemented"
    assert second.result is None
