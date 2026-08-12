import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from yt_live_dungeon.persistence.models.base import Base

SELECTABLE_ACTIONS = ("rest", "candidate_a", "candidate_b", "forge")


class RunCamp(Base):
    __tablename__ = "run_camps"
    __table_args__ = (
        UniqueConstraint("run_id", "floor", name="uq_run_camps_run_id_floor"),
        CheckConstraint(
            "candidate_a_item_id != candidate_b_item_id", name="candidates_distinct"
        ),
        CheckConstraint("deadline_at > started_at", name="deadline_after_start"),
        {"schema": "runtime"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runtime.runs.id"), nullable=False, index=True
    )
    floor: Mapped[int] = mapped_column(Integer)
    spirit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("master.spirits.id"), nullable=False
    )
    candidate_a_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("master.items.id"), nullable=False
    )
    candidate_b_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("master.items.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RunCampMember(Base):
    __tablename__ = "run_camp_members"
    __table_args__ = (
        CheckConstraint(
            f"selected_action IS NULL OR selected_action IN {SELECTABLE_ACTIONS}",
            name="selected_action_valid",
        ),
        {"schema": "runtime"},
    )

    camp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runtime.run_camps.id"), primary_key=True
    )
    run_adventurer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runtime.run_adventurers.id"),
        primary_key=True,
    )
    can_select_action: Mapped[bool] = mapped_column(Boolean, default=False)
    selected_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    selected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
