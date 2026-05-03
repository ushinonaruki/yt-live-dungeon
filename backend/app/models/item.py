from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    stat_mods: Mapped[dict] = mapped_column(JSONB, default=dict)
    attribute_mods: Mapped[dict] = mapped_column(JSONB, default=dict)
    passive_effects: Mapped[dict] = mapped_column(JSONB, default=dict)
    unlocks_spell_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("spells.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
