import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RunState(str, enum.Enum):
    WAITING = "waiting"
    BATTLE = "battle"
    RESULT = "result"
    FLOOR_TRANSITION = "floor_transition"
    GAME_OVER = "game_over"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    state: Mapped[RunState] = mapped_column(
        Enum(
            RunState,
            name="run_state",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            create_type=False,
        ),
        server_default="waiting",
        default=RunState.WAITING,
    )
    current_floor: Mapped[int] = mapped_column(Integer, default=0)
    total_deaths: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
