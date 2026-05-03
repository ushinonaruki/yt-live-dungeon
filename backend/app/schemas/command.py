from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class CommandEventIn(BaseModel):
    source: Literal["manual", "youtube", "onecomme"] = "manual"
    external_message_id: str = ""
    youtube_id: str
    display_name: str
    text: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommandResult(BaseModel):
    type: str
    processed: bool
    reason: str | None = None
