from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Logout
from yt_live_dungeon.features.run.start import start_run
from yt_live_dungeon.features.waiting.readiness import all_active_participants_ready
from yt_live_dungeon.features.waiting.session import resolve_waiting_session
from yt_live_dungeon.persistence.models import RunState
from yt_live_dungeon.persistence.queries.adventurer import list_active_participants
from yt_live_dungeon.persistence.queries.event import append_event


async def handle_logout(command: Logout, context: CommandContext) -> CommandOutcome:
    """@logout during WAITING. Per obsidian/.../ゲーム全体仕様.md section 13
    and 進行/参加受付.md section 9.2: a @logout that drops active
    participants to zero ends the run as GAME_OVER (without touching any
    death count -- Logout is never treated as a death). This can only
    ever fire after at least one @login already succeeded (there would
    be no adventurer to log out otherwise), so run.waiting_deadline_at is
    always already set by the time this branch is reachable.

    A @logout that leaves every remaining active participant READY
    starts floor 1 immediately, the same way @ready's own all-ready
    check does.
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

    adventurer.is_participating = False

    await append_event(session, run.id, "adventurer_logout", {"adventurer": str(adventurer.id)})

    remaining_participants = await list_active_participants(session, run.id)
    if not remaining_participants:
        run.state = RunState.GAME_OVER
        run.ended_at = now
        await append_event(
            session,
            run.id,
            "run_game_over",
            {"floor": run.current_floor, "reason": "no_participants"},
        )
    elif await all_active_participants_ready(session, run.id):
        await start_run(session, run, now=now, random_source=context.random_source)

    return CommandOutcome(processed=True, reason=None, result=None)
