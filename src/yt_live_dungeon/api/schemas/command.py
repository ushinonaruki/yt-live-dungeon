from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CommandRequest(BaseModel):
    source: str = Field(min_length=1, max_length=32)
    source_message_id: str = Field(min_length=1, max_length=256)
    viewer_id: str = Field(min_length=1, max_length=256)
    viewer_display_name: str
    raw_text: str
    received_at: datetime

    @field_validator("received_at")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("received_at must include a timezone offset")
        return value


class CommandResponse(BaseModel):
    processed: bool
    reason: str | None
    result: dict | None
