import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
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
        Enum(
            RunState,
            name="run_state",
            schema="runtime",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=RunState.WAITING,
    )
    current_floor: Mapped[int] = mapped_column(Integer, default=1)
    # The group already drawn and confirmed for run.current_floor + 1.
    # Never drawn "on demand" at floor start -- start_next_floor() only
    # ever consumes this. Null once floor 100 has been consumed (there
    # is no floor 101 to hold a next group for).
    next_group_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("master.enemy_groups.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
