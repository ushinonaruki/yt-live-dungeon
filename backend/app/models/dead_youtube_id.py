import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DeadYoutubeId(Base):
    __tablename__ = "dead_youtube_ids"
    __table_args__ = (
        UniqueConstraint("run_id", "youtube_id", name="uq_dead_youtube_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False, index=True
    )
    youtube_id: Mapped[str] = mapped_column(String(256))
    died_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
