import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RunAdventurer(Base):
    __tablename__ = "run_adventurers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False, index=True
    )
    youtube_id: Mapped[str] = mapped_column(String(256))
    nickname: Mapped[str] = mapped_column(String(128))
    hp: Mapped[int] = mapped_column(Integer)
    max_hp: Mapped[int] = mapped_column(Integer)
    str_val: Mapped[int] = mapped_column(Integer)
    dex_val: Mapped[int] = mapped_column(Integer)
    con_val: Mapped[int] = mapped_column(Integer)
    int_val: Mapped[int] = mapped_column(Integer)
    wis_val: Mapped[int] = mapped_column(Integer)
    cha_val: Mapped[int] = mapped_column(Integer)
    attr_red: Mapped[int] = mapped_column(Integer)
    attr_blue: Mapped[int] = mapped_column(Integer)
    attr_yellow: Mapped[int] = mapped_column(Integer)
    attr_green: Mapped[int] = mapped_column(Integer)
    attr_purple: Mapped[int] = mapped_column(Integer)
    attr_orange: Mapped[int] = mapped_column(Integer)
    attr_indigo: Mapped[int] = mapped_column(Integer)
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_floor: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    died_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
