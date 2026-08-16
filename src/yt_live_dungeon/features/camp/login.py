from yt_live_dungeon.features.adventurer.onboarding import onboard_new_adventurer
from yt_live_dungeon.features.camp.session import resolve_camp_only
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Login
from yt_live_dungeon.persistence.models import RunCampMember
from yt_live_dungeon.persistence.queries.adventurer import (
    get_adventurer_by_viewer,
    list_active_participants,
)
from yt_live_dungeon.persistence.queries.event import append_event

ALREADY_JOINED = "already_joined"
PARTY_FULL = "party_full"
MAX_PARTICIPANTS = 8


async def handle_login(command: Login, context: CommandContext) -> CommandOutcome:
    """@login only ever creates a brand-new adventurer. A youtube_id that
    has ever had a RunAdventurer row for this run -- currently
    participating, logged out, or dead -- is rejected outright and
    permanently: @logout is a one-way departure from the run, not a
    pause, so there is no "existing adventurer" branch to rejoin
    through."""
    session = context.session
    now = context.command_input.received_at
    viewer_id = context.command_input.viewer_id

    resolved = await resolve_camp_only(
        session, context.run_id, now=now, random_source=context.random_source, lock_run=True
    )
    if isinstance(resolved, CommandOutcome):
        return resolved
    run, camp = resolved.run, resolved.camp

    existing = await get_adventurer_by_viewer(session, run.id, viewer_id)
    if existing is not None:
        return CommandOutcome(processed=False, reason=ALREADY_JOINED, result=None)

    # Capacity is checked -- and the egregore/item draw happens -- only
    # after the already-exists rejection above, so neither a full camp
    # nor a repeat login ever consumes randomness or writes anything.
    current_participants = await list_active_participants(session, run.id)
    if len(current_participants) >= MAX_PARTICIPANTS:
        return CommandOutcome(processed=False, reason=PARTY_FULL, result=None)

    adventurer, granted = await onboard_new_adventurer(
        session, run, viewer_id, now, context.random_source
    )

    session.add(
        RunCampMember(
            camp_id=camp.id,
            run_adventurer_id=adventurer.id,
            can_select_action=False,
            selected_action=None,
            selected_at=None,
            ready_at=None,
            left_at=None,
        )
    )

    body = {"adventurer": str(adventurer.id), "egregore": adventurer.egregore_id, **granted}
    await append_event(session, run.id, "adventurer_login", body)

    return CommandOutcome(processed=True, reason=None, result=None)
