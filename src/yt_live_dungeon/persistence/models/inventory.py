import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from yt_live_dungeon.persistence.models.base import Base


class RunAdventurerItem(Base):
    __tablename__ = "run_adventurer_items"
    __table_args__ = (
        UniqueConstraint(
            "run_adventurer_id", "slot", name="uq_run_adventurer_items_adventurer_slot"
        ),
        UniqueConstraint(
            "run_adventurer_id", "item_id", name="uq_run_adventurer_items_adventurer_item"
        ),
        CheckConstraint("slot BETWEEN 1 AND 8", name="slot_in_range"),
        CheckConstraint("current_level >= 1", name="current_level_positive"),
        {"schema": "runtime"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_adventurer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runtime.run_adventurers.id"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("master.items.id"), nullable=False
    )
    slot: Mapped[int] = mapped_column(Integer)
    current_level: Mapped[int] = mapped_column(Integer, default=1)
    acquired_floor: Mapped[int] = mapped_column(Integer)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
