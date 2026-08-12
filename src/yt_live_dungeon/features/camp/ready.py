from yt_live_dungeon.features.camp.end import end_camp
from yt_live_dungeon.features.camp.readiness import all_active_participants_ready
from yt_live_dungeon.features.camp.session import NOT_JOINED, resolve_camp_session
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Ready
from yt_live_dungeon.persistence.queries.camp import get_camp_member
from yt_live_dungeon.persistence.queries.event import append_event

ALREADY_READY = "already_ready"


async def handle_ready(command: Ready, context: CommandContext) -> CommandOutcome:
    session = context.session
    now = context.command_input.received_at
    resolved = await resolve_camp_session(
        session,
        context.run_id,
        context.command_input.viewer_id,
        now=now,
        lock_run=True,
    )
    if isinstance(resolved, CommandOutcome):
        return resolved
    run, camp, adventurer = resolved.run, resolved.camp, resolved.adventurer

    member = await get_camp_member(session, camp.id, adventurer.id)
    if member is None:
        return CommandOutcome(processed=False, reason=NOT_JOINED, result=None)
    if member.ready_at is not None:
        return CommandOutcome(processed=False, reason=ALREADY_READY, result=None)

    member.ready_at = now
    await append_event(
        session,
        run.id,
        "adventurer_ready",
        {"adventurer": str(adventurer.id), "reason": "manual"},
    )

    if await all_active_participants_ready(session, run.id, camp.id):
        await end_camp(session, run, camp, now=now, reason="all_ready")

    return CommandOutcome(processed=True, reason=None, result=None)
