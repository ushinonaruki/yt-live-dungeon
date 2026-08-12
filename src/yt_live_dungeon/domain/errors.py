class DomainError(Exception):
    """Base type for pure-domain validation failures."""


class InvalidStatModifierError(DomainError):
    pass


class CampConfigurationError(DomainError):
    """Raised when master data can't support starting a CAMP (e.g. a
    spirit's active item pool has fewer than 2 entries)."""


class LoginConfigurationError(DomainError):
    """Raised when master data can't support onboarding a new adventurer
    (no active spirits, or the drawn spirit's active item pool is
    empty)."""


class EnemyGroupConfigurationError(DomainError):
    """Raised when master data can't support starting a floor (no active
    enemy groups to draw from, or a saved next_group_id no longer
    resolves to a valid, complete group)."""


class InvalidEnemyAttributesError(DomainError):
    """Raised when a RunEnemy's snapshotted 10-attribute dict is missing
    a key, has an extra key, or has a non-integer value."""


class InvalidParticipantCountError(DomainError):
    """Raised when a floor is about to be spawned for a participant
    count outside the 1-8 range that determines enemy MP regen rate
    (obsidian/.../ダンジョン/フロア補正.md section 5). 0 participants
    is a caller-responsibility failure -- callers must branch to RETIRE
    (or equivalent) before ever reaching group spawn, not rely on this
    to degrade gracefully."""
