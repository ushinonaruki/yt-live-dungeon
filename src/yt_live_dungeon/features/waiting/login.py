from datetime import timedelta

from yt_live_dungeon.features.adventurer.onboarding import onboard_new_adventurer
from yt_live_dungeon.features.commands.context import CommandContext
from yt_live_dungeon.features.commands.dispatch import CommandOutcome
from yt_live_dungeon.features.commands.parse import Login
from yt_live_dungeon.features.waiting.session import resolve_waiting_only
from yt_live_dungeon.persistence.queries.adventurer import (
    get_adventurer_by_viewer,
    list_active_participants,
)
from yt_live_dungeon.persistence.queries.event import append_event

ALREADY_JOINED = "already_joined"
PARTY_FULL = "party_full"
MAX_PARTICIPANTS = 8

# obsidian/.../進行/参加受付.md section 6: the initial-participation
# deadline is exactly 5 minutes from the first successful @login.
INITIAL_PARTICIPATION_WINDOW = timedelta(minutes=5)


async def handle_login(command: Login, context: CommandContext) -> CommandOutcome:
    """@login during WAITING. Shares onboarding rules with CAMP's @login
    (features/adventurer/onboarding.py) but, unlike CAMP, has no
    RunCamp/RunCampMember row to attach to -- WAITING participation and
    READY state live directly on RunAdventurer (is_participating,
    waiting_ready_at).

    Only the very first adventurer to ever successfully join this run
    starts the initial-participation deadline
    (run.waiting_deadline_at); every later @login leaves an
    already-set deadline untouched, and a rejected @login (already
    joined, party full) never touches it at all.
    """
    session = context.session
    now = context.command_input.received_at
    viewer_id = context.command_input.viewer_id

    resolved = await resolve_waiting_only(
        session, context.run_id, now=now, random_source=context.random_source, lock_run=True
    )
    if isinstance(resolved, CommandOutcome):
        return resolved
    run = resolved.run

    existing = await get_adventurer_by_viewer(session, run.id, viewer_id)
    if existing is not None:
        return CommandOutcome(processed=False, reason=ALREADY_JOINED, result=None)

    # Capacity is checked -- and the spirit/item draw happens -- only
    # after the already-exists rejection above, so neither a full run
    # nor a repeat login ever consumes randomness or writes anything.
    current_participants = await list_active_participants(session, run.id)
    if len(current_participants) >= MAX_PARTICIPANTS:
        return CommandOutcome(processed=False, reason=PARTY_FULL, result=None)

    adventurer, granted = await onboard_new_adventurer(
        session, run, viewer_id, now, context.random_source
    )

    if run.waiting_deadline_at is None:
        run.waiting_deadline_at = now + INITIAL_PARTICIPATION_WINDOW

    body = {"adventurer": str(adventurer.id), "spirit": adventurer.spirit_id, **granted}
    await append_event(session, run.id, "adventurer_login", body)

    return CommandOutcome(processed=True, reason=None, result=None)
