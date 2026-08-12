from collections.abc import Sequence
from typing import Protocol, TypeVar

T = TypeVar("T")


class RandomSource(Protocol):
    """Anything shaped like `random.Random` for the sampling this app needs.

    Injected so callers can pass a seeded `random.Random` in tests instead
    of depending on global random state.
    """

    def sample(self, population: Sequence[T], k: int) -> list[T]: ...
