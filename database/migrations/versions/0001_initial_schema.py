"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-02 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE run_state AS ENUM "
        "('waiting', 'battle', 'result', 'floor_transition', 'game_over')"
    )

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "state",
            postgresql.ENUM(
                "waiting",
                "battle",
                "result",
                "floor_transition",
                "game_over",
                name="run_state",
                create_type=False,
            ),
            nullable=False,
            server_default="waiting",
        ),
        sa.Column("current_floor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_deaths", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "spells",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("formula", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("cooldown_seconds", sa.Float(), nullable=False, server_default="3.0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint("name", name="uq_spells_name"),
    )

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("stat_mods", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "attribute_mods", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "passive_effects", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "unlocks_spell_id", sa.Integer(), sa.ForeignKey("spells.id"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint("name", name="uq_items_name"),
    )

    op.create_table(
        "enemies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("base_hp", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("base_barrier", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "special_actions", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "greeting_action", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint("name", name="uq_enemies_name"),
    )

    op.create_table(
        "enemy_spell_defs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "enemy_id", sa.Integer(), sa.ForeignKey("enemies.id"), nullable=False
        ),
        sa.Column("display_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("cooldown_seconds", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column(
            "trigger_conditions",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("formula", postgresql.JSONB(), nullable=False, server_default="{}"),
    )

    op.create_table(
        "enemy_item_defs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "enemy_id", sa.Integer(), sa.ForeignKey("enemies.id"), nullable=False
        ),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "nickname_words",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("word", sa.String(64), nullable=False),
        sa.Column("part", sa.String(16), nullable=False),
    )

    op.create_table(
        "commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id"),
            nullable=False,
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "external_message_id", sa.String(256), nullable=False, server_default=""
        ),
        sa.Column("youtube_id", sa.String(256), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_commands_run_id", "commands", ["run_id"])

    op.create_table(
        "logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("body", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_logs_run_id", "logs", ["run_id"])

    op.create_table(
        "run_adventurers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id"),
            nullable=False,
        ),
        sa.Column("youtube_id", sa.String(256), nullable=False),
        sa.Column("nickname", sa.String(128), nullable=False),
        sa.Column("hp", sa.Integer(), nullable=False),
        sa.Column("max_hp", sa.Integer(), nullable=False),
        sa.Column("str_val", sa.Integer(), nullable=False),
        sa.Column("dex_val", sa.Integer(), nullable=False),
        sa.Column("con_val", sa.Integer(), nullable=False),
        sa.Column("int_val", sa.Integer(), nullable=False),
        sa.Column("wis_val", sa.Integer(), nullable=False),
        sa.Column("cha_val", sa.Integer(), nullable=False),
        sa.Column("attr_red", sa.Integer(), nullable=False),
        sa.Column("attr_blue", sa.Integer(), nullable=False),
        sa.Column("attr_yellow", sa.Integer(), nullable=False),
        sa.Column("attr_green", sa.Integer(), nullable=False),
        sa.Column("attr_purple", sa.Integer(), nullable=False),
        sa.Column("attr_orange", sa.Integer(), nullable=False),
        sa.Column("attr_indigo", sa.Integer(), nullable=False),
        sa.Column("is_alive", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("joined_floor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("died_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_run_adventurers_run_id", "run_adventurers", ["run_id"])

    op.create_table(
        "run_enemies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id"),
            nullable=False,
        ),
        sa.Column(
            "enemy_id", sa.Integer(), sa.ForeignKey("enemies.id"), nullable=False
        ),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("hp", sa.Integer(), nullable=False),
        sa.Column("max_hp", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("barrier", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_alive", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("died_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_run_enemies_run_id", "run_enemies", ["run_id"])

    op.create_table(
        "run_adventurer_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_adventurer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("run_adventurers.id"),
            nullable=False,
        ),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("acquired_floor", sa.Integer(), nullable=False),
        sa.Column(
            "acquired_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "run_adventurer_id", "slot", name="uq_run_adventurer_item_slot"
        ),
        sa.CheckConstraint(
            "slot >= 1 AND slot <= 9", name="ck_run_adventurer_item_slot"
        ),
    )
    op.create_index(
        "ix_run_adventurer_items_run_adventurer_id",
        "run_adventurer_items",
        ["run_adventurer_id"],
    )

    op.create_table(
        "run_status_accumulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status_type", sa.String(32), nullable=False),
        sa.Column("accumulation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_run_status_accumulations_run_id", "run_status_accumulations", ["run_id"]
    )

    op.create_table(
        "run_active_statuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status_type", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_run_active_statuses_run_id", "run_active_statuses", ["run_id"])

    op.create_table(
        "run_pending_joins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id"),
            nullable=False,
        ),
        sa.Column("youtube_id", sa.String(256), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column(
            "command_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commands.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint("run_id", "youtube_id", name="uq_pending_join"),
    )
    op.create_index("ix_run_pending_joins_run_id", "run_pending_joins", ["run_id"])

    op.create_table(
        "run_result_choices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id"),
            nullable=False,
        ),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column(
            "run_adventurer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("run_adventurers.id"),
            nullable=False,
        ),
        sa.Column("choice", sa.Boolean(), nullable=False),
        sa.Column(
            "command_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commands.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_run_result_choices_run_id", "run_result_choices", ["run_id"])

    op.create_table(
        "dead_youtube_ids",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id"),
            nullable=False,
        ),
        sa.Column("youtube_id", sa.String(256), nullable=False),
        sa.Column("died_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "youtube_id", name="uq_dead_youtube_id"),
    )
    op.create_index("ix_dead_youtube_ids_run_id", "dead_youtube_ids", ["run_id"])


def downgrade() -> None:
    op.drop_table("dead_youtube_ids")
    op.drop_table("run_result_choices")
    op.drop_table("run_pending_joins")
    op.drop_table("run_active_statuses")
    op.drop_table("run_status_accumulations")
    op.drop_table("run_adventurer_items")
    op.drop_table("run_enemies")
    op.drop_table("run_adventurers")
    op.drop_table("logs")
    op.drop_table("commands")
    op.drop_table("nickname_words")
    op.drop_table("enemy_item_defs")
    op.drop_table("enemy_spell_defs")
    op.drop_table("enemies")
    op.drop_table("items")
    op.drop_table("spells")
    op.drop_table("runs")
    op.execute("DROP TYPE IF EXISTS run_state")
