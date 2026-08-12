from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CommandInput:
    """Normalized command input, independent of the originating adapter
    (YouTube Live, Unity, tests, ...)."""

    source: str
    source_message_id: str
    viewer_id: str
    viewer_display_name: str
    raw_text: str
    received_at: datetime
