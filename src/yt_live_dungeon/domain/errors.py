class DomainError(Exception):
    """Base type for pure-domain validation failures."""


class InvalidStatModifierError(DomainError):
    pass
