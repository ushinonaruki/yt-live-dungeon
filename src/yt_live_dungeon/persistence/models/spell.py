from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from yt_live_dungeon.domain.attributes import ATTRIBUTE_CODES
from yt_live_dungeon.persistence.models.base import Base


class Spell(Base):
    __tablename__ = "spells"
    __table_args__ = (
        CheckConstraint(f"attribute IN {ATTRIBUTE_CODES}", name="attribute_valid"),
        CheckConstraint("mp_cost >= 0", name="mp_cost_non_negative"),
        CheckConstraint(
            "jsonb_typeof(effects) = 'array' AND jsonb_array_length(effects) >= 1",
            name="effects_non_empty_array",
        ),
        {"schema": "master"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    command: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    attribute: Mapped[str] = mapped_column(String(2))
    mp_cost: Mapped[int] = mapped_column(Integer)
    target_rule: Mapped[str] = mapped_column(String(32))
    effects: Mapped[list] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
