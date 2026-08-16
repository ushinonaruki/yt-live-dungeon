from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from yt_live_dungeon.domain.attributes import ATTRIBUTE_CODES
from yt_live_dungeon.persistence.models.base import Base


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint(f"attribute IN {ATTRIBUTE_CODES}", name="attribute_valid"),
        # obsidian/.../アイテム/アイテム定義仕様.md section 7: max MP is
        # fixed at 100 for every combatant, so item stat modifiers may
        # never carry a "max_mp" key.
        CheckConstraint(
            "NOT (base_stat_modifiers ? 'max_mp')", name="base_stat_modifiers_no_max_mp"
        ),
        CheckConstraint(
            "NOT (per_level_stat_modifiers ? 'max_mp')", name="per_level_stat_modifiers_no_max_mp"
        ),
        {"schema": "master"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_key: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    attribute: Mapped[str] = mapped_column(String(2))
    granted_spell_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("master.spells.id"), nullable=False
    )
    base_stat_modifiers: Mapped[dict] = mapped_column(JSONB, default=dict)
    per_level_stat_modifiers: Mapped[dict] = mapped_column(JSONB, default=dict)
    break_effects: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
