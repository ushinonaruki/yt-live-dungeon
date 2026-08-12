from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from yt_live_dungeon.domain.attributes import ATTRIBUTE_CODES
from yt_live_dungeon.persistence.models.base import Base


class Spirit(Base):
    __tablename__ = "spirits"
    __table_args__ = (
        CheckConstraint(
            f"representative_attribute IN {ATTRIBUTE_CODES}",
            name="representative_attribute_valid",
        ),
        {"schema": "master"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    spirit_key: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    representative_attribute: Mapped[str] = mapped_column(String(2))
    blessing_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("master.items.id"), unique=True, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SpiritItemPoolEntry(Base):
    __tablename__ = "spirit_item_pool_entries"
    __table_args__ = {"schema": "master"}

    spirit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("master.spirits.id"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("master.items.id"), primary_key=True
    )
