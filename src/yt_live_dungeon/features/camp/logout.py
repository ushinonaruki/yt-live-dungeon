from yt_live_dungeon.features.camp.end import end_camp
from yt_live_dungeon.features.camp.readiness import all_active_participants_ready
from yt_live_dungeon.features.camp.session import resolve_camp_session
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Logout
from yt_live_dungeon.persistence.queries.adventurer import list_active_participants
from yt_live_dungeon.persistence.queries.camp import get_camp_member
from yt_live_dungeon.persistence.queries.event import append_event


async def handle_logout(command: Logout, context: CommandContext) -> CommandOutcome:
    session = context.session
    now = context.command_input.received_at
    resolved = await resolve_camp_session(
        session,
        context.run_id,
        context.command_input.viewer_id,
        now=now,
        random_source=context.random_source,
        lock_run=True,
    )
    if isinstance(resolved, CommandOutcome):
        return resolved
    run, camp, adventurer = resolved.run, resolved.camp, resolved.adventurer

    # Participation flips off; the adventurer row itself (spirit, items,
    # item levels, hp, mp) is left untouched, as is the RunCampMember row
    # apart from left_at -- a logged-out survivor keeps their history.
    adventurer.is_participating = False

    member = await get_camp_member(session, camp.id, adventurer.id)
    if member is not None:
        member.left_at = now

    await append_event(session, run.id, "adventurer_logout", {"adventurer": str(adventurer.id)})

    remaining_participants = await list_active_participants(session, run.id)
    if not remaining_participants:
        await end_camp(
            session, run, camp, now=now, reason="empty", random_source=context.random_source
        )
    elif await all_active_participants_ready(session, run.id, camp.id):
        await end_camp(
            session, run, camp, now=now, reason="all_ready", random_source=context.random_source
        )

    return CommandOutcome(processed=True, reason=None, result=None)
