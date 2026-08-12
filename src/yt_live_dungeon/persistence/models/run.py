import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from yt_live_dungeon.persistence.models.base import Base


class RunState(enum.StrEnum):
    WAITING = "waiting"
    BATTLE = "battle"
    CAMP = "camp"
    RETIRE = "retire"
    GAME_OVER = "game_over"


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = {"schema": "runtime"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    state: Mapped[RunState] = mapped_column(
        Enum(RunState, name="run_state", schema="runtime"),
        default=RunState.WAITING,
    )
    current_floor: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
