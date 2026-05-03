from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import (
    JSONB,
)  # special_actions, greeting_action, formula で使用
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Enemy(Base):
    __tablename__ = "enemies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    base_hp: Mapped[int] = mapped_column(Integer, default=100)

    special_actions: Mapped[list] = mapped_column(JSONB, default=list)
    greeting_action: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EnemySpellDef(Base):
    __tablename__ = "enemy_spell_defs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enemy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("enemies.id"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(128), default="")
    cooldown_seconds: Mapped[float] = mapped_column(Float, default=5.0)
    trigger_conditions: Mapped[dict] = mapped_column(JSONB, default=dict)
    formula: Mapped[dict] = mapped_column(JSONB, default=dict)


class EnemyItemDef(Base):
    __tablename__ = "enemy_item_defs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enemy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("enemies.id"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.id"), nullable=False
    )
    weight: Mapped[int] = mapped_column(Integer, default=1)
