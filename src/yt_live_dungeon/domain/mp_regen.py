from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class MpRegenOutcome:
    mp: int
    updated_at: datetime


def apply_mp_regen(
    *, mp: int, max_mp: int, regen_rate: int, updated_at: datetime, now: datetime
) -> MpRegenOutcome:
    """Pure MP natural-regen catch-up, entity-agnostic: works for any
    combatant with an MP value, a max, a per-second regen rate, and a
    persisted regen anchor timestamp -- not specific to enemies, so a
    future adventurer-side implementation can reuse this unchanged.

    Only whole elapsed seconds are consumed and folded into the
    returned `updated_at`; a sub-second remainder is left in place for
    the next catch-up, so the total regen over any span is independent
    of how often this is called. A non-positive elapsed duration (equal
    or earlier `now`, e.g. from clock skew) yields no change at all --
    MP and the anchor never move backward.
    """
    elapsed_seconds = int((now - updated_at).total_seconds())
    if elapsed_seconds <= 0:
        return MpRegenOutcome(mp=mp, updated_at=updated_at)

    new_mp = min(max_mp, mp + elapsed_seconds * regen_rate)
    new_updated_at = updated_at + timedelta(seconds=elapsed_seconds)
    return MpRegenOutcome(mp=new_mp, updated_at=new_updated_at)
