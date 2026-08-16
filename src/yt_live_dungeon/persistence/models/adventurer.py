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
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from yt_live_dungeon.persistence.models.base import Base


class RunAdventurer(Base):
    __tablename__ = "run_adventurers"
    __table_args__ = (
        UniqueConstraint("run_id", "youtube_id", name="uq_run_adventurers_run_id_youtube_id"),
        # obsidian/.../キャラクター/ステータス.md section 5: max MP is
        # fixed at 100 for every combatant, never adjustable by items.
        CheckConstraint("base_max_mp = 100", name="base_max_mp_fixed_100"),
        CheckConstraint("mp >= 0", name="mp_non_negative"),
        CheckConstraint("mp <= 100", name="mp_within_max"),
        {"schema": "runtime"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runtime.runs.id"), nullable=False, index=True
    )
    youtube_id: Mapped[str] = mapped_column(String(256))
    hp: Mapped[int] = mapped_column(Integer)
    mp: Mapped[int] = mapped_column(Integer)
    base_max_hp: Mapped[int] = mapped_column(Integer, default=500)
    base_max_mp: Mapped[int] = mapped_column(Integer, default=100)
    spirit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("master.spirits.id"), nullable=True
    )
    is_participating: Mapped[bool] = mapped_column(Boolean, default=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # READY state during the run's initial WAITING participation window
    # only (obsidian/.../進行/参加受付.md section 7). Distinct from
    # RunCampMember.ready_at, which tracks READY per floor's CAMP
    # instead -- WAITING has no RunCamp row to attach a membership-style
    # ready flag to, and happens at most once per run.
    waiting_ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
