"""enemy groups and run enemies

Revision ID: b195bebfaf29
Revises: 9b9080e6af23
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b195bebfaf29'
down_revision: Union[str, None] = '9b9080e6af23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('enemy_groups',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('group_key', sa.String(length=64), nullable=False),
    sa.Column('display_name', sa.String(length=128), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_enemy_groups')),
    sa.UniqueConstraint('group_key', name=op.f('uq_enemy_groups_group_key')),
    schema='master'
    )
    op.create_table('enemy_group_members',
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('order_in_group', sa.Integer(), nullable=False),
    sa.Column('enemy_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.CheckConstraint("role IN ('master', 'minion')", name=op.f('ck_enemy_group_members_role_valid')),
    sa.CheckConstraint('order_in_group BETWEEN 1 AND 9', name=op.f('ck_enemy_group_members_order_in_group_in_range')),
    sa.ForeignKeyConstraint(['enemy_id'], ['master.enemies.id'], name=op.f('fk_enemy_group_members_enemy_id_enemies')),
    sa.ForeignKeyConstraint(['group_id'], ['master.enemy_groups.id'], name=op.f('fk_enemy_group_members_group_id_enemy_groups')),
    sa.PrimaryKeyConstraint('group_id', 'order_in_group', name=op.f('pk_enemy_group_members')),
    schema='master'
    )
    # At most one master per group. "At least one master" and "at most 8
    # minions" require counting sibling rows and are enforced at the
    # application boundary (group registration), not by this index.
    op.create_index(
        'uq_enemy_group_members_one_master_per_group',
        'enemy_group_members',
        ['group_id'],
        unique=True,
        schema='master',
        postgresql_where=sa.text("role = 'master'"),
    )

    op.add_column(
        'runs',
        sa.Column('next_group_id', sa.Integer(), nullable=True),
        schema='runtime',
    )
    op.create_foreign_key(
        op.f('fk_runs_next_group_id_enemy_groups'),
        'runs', 'enemy_groups',
        ['next_group_id'], ['id'],
        source_schema='runtime', referent_schema='master',
    )

    op.create_table('run_enemies',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('floor', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('enemy_id', sa.Integer(), nullable=False),
    sa.Column('order_in_group', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('max_hp', sa.Integer(), nullable=False),
    sa.Column('hp', sa.Integer(), nullable=False),
    sa.Column('max_mp', sa.Integer(), nullable=False),
    sa.Column('mp', sa.Integer(), nullable=False),
    sa.Column('mp_regen_rate', sa.Integer(), nullable=False),
    sa.Column('mp_regen_updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('defeated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('master', 'minion')", name=op.f('ck_run_enemies_role_valid')),
    sa.CheckConstraint('order_in_group >= 1', name=op.f('ck_run_enemies_order_in_group_positive')),
    sa.CheckConstraint('max_hp >= 0', name=op.f('ck_run_enemies_max_hp_non_negative')),
    sa.CheckConstraint('hp >= 0', name=op.f('ck_run_enemies_hp_non_negative')),
    sa.CheckConstraint('hp <= max_hp', name=op.f('ck_run_enemies_hp_within_max')),
    sa.CheckConstraint('max_mp >= 0', name=op.f('ck_run_enemies_max_mp_non_negative')),
    sa.CheckConstraint('mp >= 0', name=op.f('ck_run_enemies_mp_non_negative')),
    sa.CheckConstraint('mp <= max_mp', name=op.f('ck_run_enemies_mp_within_max')),
    sa.CheckConstraint('mp_regen_rate BETWEEN 1 AND 8', name=op.f('ck_run_enemies_mp_regen_rate_in_range')),
    sa.ForeignKeyConstraint(['enemy_id'], ['master.enemies.id'], name=op.f('fk_run_enemies_enemy_id_enemies')),
    sa.ForeignKeyConstraint(['group_id'], ['master.enemy_groups.id'], name=op.f('fk_run_enemies_group_id_enemy_groups')),
    sa.ForeignKeyConstraint(['run_id'], ['runtime.runs.id'], name=op.f('fk_run_enemies_run_id_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_run_enemies')),
    sa.UniqueConstraint('run_id', 'floor', 'order_in_group', name='uq_run_enemies_run_floor_order'),
    schema='runtime'
    )
    op.create_index(op.f('ix_runtime_run_enemies_run_id'), 'run_enemies', ['run_id'], unique=False, schema='runtime')
    # Exactly one master per run+floor.
    op.create_index(
        'uq_run_enemies_one_master_per_run_floor',
        'run_enemies',
        ['run_id', 'floor'],
        unique=True,
        schema='runtime',
        postgresql_where=sa.text("role = 'master'"),
    )


def downgrade() -> None:
    op.drop_index('uq_run_enemies_one_master_per_run_floor', table_name='run_enemies', schema='runtime')
    op.drop_index(op.f('ix_runtime_run_enemies_run_id'), table_name='run_enemies', schema='runtime')
    op.drop_table('run_enemies', schema='runtime')
    op.drop_constraint(op.f('fk_runs_next_group_id_enemy_groups'), 'runs', schema='runtime', type_='foreignkey')
    op.drop_column('runs', 'next_group_id', schema='runtime')
    op.drop_index('uq_enemy_group_members_one_master_per_group', table_name='enemy_group_members', schema='master')
    op.drop_table('enemy_group_members', schema='master')
    op.drop_table('enemy_groups', schema='master')
