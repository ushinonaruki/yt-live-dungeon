from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from yt_live_dungeon.persistence.models.base import Base

ENEMY_GROUP_MEMBER_ROLES = ("master", "minion")


class EnemyGroup(Base):
    """A pre-registered, fixed group of enemies that can appear on a
    floor: exactly one master plus 0-8 minions. Groups are drawn whole
    (never assembled per-floor) -- see EnemyGroupMember."""

    __tablename__ = "enemy_groups"
    __table_args__ = {"schema": "master"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_key: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EnemyGroupMember(Base):
    """One fixed slot in an EnemyGroup's composition. order_in_group is
    part of the primary key, so a group can never have two members at
    the same position. A partial unique index (see the migration)
    additionally guarantees at most one 'master' row per group; "at
    least one master" and "at most 8 minions" require counting sibling
    rows and are enforced at the application boundary (group
    registration), not by a single-row CHECK constraint."""

    __tablename__ = "enemy_group_members"
    __table_args__ = (
        CheckConstraint(f"role IN {ENEMY_GROUP_MEMBER_ROLES}", name="role_valid"),
        CheckConstraint("order_in_group BETWEEN 1 AND 9", name="order_in_group_in_range"),
        {"schema": "master"},
    )

    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("master.enemy_groups.id"), primary_key=True
    )
    order_in_group: Mapped[int] = mapped_column(Integer, primary_key=True)
    enemy_id: Mapped[int] = mapped_column(Integer, ForeignKey("master.enemies.id"))
    role: Mapped[str] = mapped_column(String(16))
