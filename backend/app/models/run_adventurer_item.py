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

from app.db.base import Base


class RunAdventurerItem(Base):
    __tablename__ = "run_adventurer_items"
    __table_args__ = (
        UniqueConstraint(
            "run_adventurer_id", "slot", name="uq_run_adventurer_item_slot"
        ),
        CheckConstraint("slot >= 1 AND slot <= 9", name="ck_run_adventurer_item_slot"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_adventurer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("run_adventurers.id"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.id"), nullable=False
    )
    slot: Mapped[int] = mapped_column(Integer)
    acquired_floor: Mapped[int] = mapped_column(Integer)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
