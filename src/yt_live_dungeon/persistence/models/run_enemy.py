import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from yt_live_dungeon.persistence.models.base import Base

RUN_ENEMY_ROLES = ("master", "minion")


class RunEnemy(Base):
    """One enemy actually spawned on a specific run's specific floor,
    with its floor-scaled stats snapshotted at creation time -- later
    changes to the referenced Enemy/EnemyGroup master data never affect
    an already-spawned floor's combat values, role, or position.

    order_in_group has no upper-bound CHECK (unlike EnemyGroupMember's
    1-9 template range): a future "additional spawn during battle"
    feature may need order values beyond the initial group's 1-9, and
    this schema must not block that.

    mp_regen_rate/mp_regen_updated_at are snapshotted once at spawn
    time from the floor-start participant count (see
    features/floor/spawn.py) and never recomputed afterward -- a
    participant logging out or dying mid-floor must not change an
    already-spawned enemy's regen rate. The 1-8 CHECK mirrors the CAMP
    participant cap (obsidian/.../ダンジョン/フロア補正.md section 5)
    as a hard runtime invariant: spawn_group() must refuse to create any
    row here at all when the floor-start participant count is outside
    that range, rather than let a 0-9999 rate slip into this table.
    """

    __tablename__ = "run_enemies"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "floor", "order_in_group", name="uq_run_enemies_run_floor_order"
        ),
        CheckConstraint(f"role IN {RUN_ENEMY_ROLES}", name="role_valid"),
        CheckConstraint("order_in_group >= 1", name="order_in_group_positive"),
        CheckConstraint("max_hp >= 0", name="max_hp_non_negative"),
        CheckConstraint("hp >= 0", name="hp_non_negative"),
        CheckConstraint("hp <= max_hp", name="hp_within_max"),
        CheckConstraint("max_mp >= 0", name="max_mp_non_negative"),
        # obsidian/.../キャラクター/ステータス.md section 5: max MP is
        # fixed at 100 for every combatant, never varied by floor or
        # participant count.
        CheckConstraint("max_mp = 100", name="max_mp_fixed_100"),
        CheckConstraint("mp >= 0", name="mp_non_negative"),
        CheckConstraint("mp <= max_mp", name="mp_within_max"),
        CheckConstraint("mp_regen_rate BETWEEN 1 AND 8", name="mp_regen_rate_in_range"),
        {"schema": "runtime"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runtime.runs.id"), nullable=False, index=True
    )
    floor: Mapped[int] = mapped_column(Integer)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("master.enemy_groups.id"))
    enemy_id: Mapped[int] = mapped_column(Integer, ForeignKey("master.enemies.id"))
    order_in_group: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    max_hp: Mapped[int] = mapped_column(Integer)
    hp: Mapped[int] = mapped_column(Integer)
    max_mp: Mapped[int] = mapped_column(Integer)
    mp: Mapped[int] = mapped_column(Integer)
    mp_regen_rate: Mapped[int] = mapped_column(Integer)
    mp_regen_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attributes: Mapped[dict] = mapped_column(JSONB)
    defeated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
