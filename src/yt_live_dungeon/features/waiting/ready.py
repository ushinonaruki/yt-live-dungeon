from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Ready
from yt_live_dungeon.features.run.start import start_run
from yt_live_dungeon.features.waiting.readiness import all_active_participants_ready
from yt_live_dungeon.features.waiting.session import resolve_waiting_session
from yt_live_dungeon.persistence.queries.event import append_event

ALREADY_READY = "already_ready"


async def handle_ready(command: Ready, context: CommandContext) -> CommandOutcome:
    """@ready during WAITING. Per obsidian/.../進行/参加受付.md section 8:
    once every currently active participant is READY, floor 1 starts
    immediately via the existing start_run() -- the 5-minute deadline is
    a separate, independent trigger for the same transition (see
    features/waiting/deadline.py), not something this checks itself.
    """
    session = context.session
    now = context.command_input.received_at
    resolved = await resolve_waiting_session(
        session,
        context.run_id,
        context.command_input.viewer_id,
        now=now,
        random_source=context.random_source,
        lock_run=True,
    )
    if isinstance(resolved, CommandOutcome):
        return resolved
    run, adventurer = resolved.run, resolved.adventurer

    if adventurer.waiting_ready_at is not None:
        return CommandOutcome(processed=False, reason=ALREADY_READY, result=None)

    adventurer.waiting_ready_at = now
    await append_event(
        session,
        run.id,
        "adventurer_ready",
        {"adventurer": str(adventurer.id), "reason": "manual"},
    )

    if await all_active_participants_ready(session, run.id):
        await start_run(session, run, now=now, random_source=context.random_source)

    return CommandOutcome(processed=True, reason=None, result=None)
