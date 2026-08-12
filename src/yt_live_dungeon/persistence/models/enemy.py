from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from yt_live_dungeon.domain.attributes import ATTRIBUTE_CODES
from yt_live_dungeon.persistence.models.base import Base


class Enemy(Base):
    __tablename__ = "enemies"
    __table_args__ = (
        CheckConstraint(
            f"weak_attribute IS NULL OR weak_attribute IN {ATTRIBUTE_CODES}",
            name="weak_attribute_valid",
        ),
        CheckConstraint("break_max >= 0", name="break_max_non_negative"),
        {"schema": "master"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enemy_key: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    base_max_hp: Mapped[int] = mapped_column(Integer)
    base_max_mp: Mapped[int] = mapped_column(Integer)
    base_attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    weak_attribute: Mapped[str | None] = mapped_column(String(2), nullable=True)
    break_max: Mapped[int] = mapped_column(Integer)
    ai_policy_key: Mapped[str] = mapped_column(String(64), default="random_v1")
    ai_policy_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EnemySpell(Base):
    __tablename__ = "enemy_spells"
    __table_args__ = {"schema": "master"}

    enemy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("master.enemies.id"), primary_key=True
    )
    spell_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("master.spells.id"), primary_key=True
    )
