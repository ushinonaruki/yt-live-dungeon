from datetime import datetime

from pydantic import BaseModel


class EventResponse(BaseModel):
    sequence: int
    event_type: str
    body: dict
    created_at: datetime


class EventListResponse(BaseModel):
    events: list[EventResponse]
