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
