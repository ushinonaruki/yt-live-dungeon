"""fix max mp to 100

Revision ID: 7c2a9e4f1b3d
Revises: 16431f96c0b7
Create Date: 2026-08-16 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = '7c2a9e4f1b3d'
down_revision: Union[str, None] = '16431f96c0b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize any pre-existing data to the fixed max_mp=100 rule
    # (obsidian/.../キャラクター/ステータス.md section 5) before adding
    # the CHECK constraints below, so the constraints can never fail to
    # attach against rows written before this fix existed.
    op.execute("UPDATE master.enemies SET base_max_mp = 100")
    op.execute("UPDATE runtime.run_adventurers SET base_max_mp = 100")
    op.execute(
        "UPDATE runtime.run_adventurers SET mp = LEAST(GREATEST(mp, 0), 100) "
        "WHERE mp < 0 OR mp > 100"
    )
    op.execute("UPDATE runtime.run_enemies SET max_mp = 100")
    op.execute(
        "UPDATE runtime.run_enemies SET mp = LEAST(GREATEST(mp, 0), 100) "
        "WHERE mp < 0 OR mp > 100"
    )
    op.execute(
        "UPDATE master.items SET base_stat_modifiers = base_stat_modifiers - 'max_mp' "
        "WHERE base_stat_modifiers ? 'max_mp'"
    )
    op.execute(
        "UPDATE master.items SET per_level_stat_modifiers = per_level_stat_modifiers - 'max_mp' "
        "WHERE per_level_stat_modifiers ? 'max_mp'"
    )

    op.create_check_constraint(
        op.f('ck_enemies_base_max_mp_fixed_100'), 'enemies', 'base_max_mp = 100', schema='master',
    )
    op.create_check_constraint(
        op.f('ck_run_adventurers_base_max_mp_fixed_100'), 'run_adventurers',
        'base_max_mp = 100', schema='runtime',
    )
    op.create_check_constraint(
        op.f('ck_run_adventurers_mp_non_negative'), 'run_adventurers', 'mp >= 0', schema='runtime',
    )
    op.create_check_constraint(
        op.f('ck_run_adventurers_mp_within_max'), 'run_adventurers', 'mp <= 100', schema='runtime',
    )
    op.create_check_constraint(
        op.f('ck_run_enemies_max_mp_fixed_100'), 'run_enemies', 'max_mp = 100', schema='runtime',
    )
    op.create_check_constraint(
        op.f('ck_items_base_stat_modifiers_no_max_mp'), 'items',
        "NOT (base_stat_modifiers ? 'max_mp')", schema='master',
    )
    op.create_check_constraint(
        op.f('ck_items_per_level_stat_modifiers_no_max_mp'), 'items',
        "NOT (per_level_stat_modifiers ? 'max_mp')", schema='master',
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('ck_items_per_level_stat_modifiers_no_max_mp'), 'items',
        schema='master', type_='check',
    )
    op.drop_constraint(
        op.f('ck_items_base_stat_modifiers_no_max_mp'), 'items',
        schema='master', type_='check',
    )
    op.drop_constraint(
        op.f('ck_run_enemies_max_mp_fixed_100'), 'run_enemies',
        schema='runtime', type_='check',
    )
    op.drop_constraint(
        op.f('ck_run_adventurers_mp_within_max'), 'run_adventurers',
        schema='runtime', type_='check',
    )
    op.drop_constraint(
        op.f('ck_run_adventurers_mp_non_negative'), 'run_adventurers',
        schema='runtime', type_='check',
    )
    op.drop_constraint(
        op.f('ck_run_adventurers_base_max_mp_fixed_100'), 'run_adventurers',
        schema='runtime', type_='check',
    )
    op.drop_constraint(
        op.f('ck_enemies_base_max_mp_fixed_100'), 'enemies',
        schema='master', type_='check',
    )
