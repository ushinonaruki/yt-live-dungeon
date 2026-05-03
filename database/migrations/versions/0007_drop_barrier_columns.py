"""drop barrier columns from run_enemies and enemies

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("run_enemies", "barrier")
    op.drop_column("enemies", "base_barrier")


def downgrade() -> None:
    op.add_column(
        "enemies",
        sa.Column("base_barrier", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "run_enemies",
        sa.Column("barrier", sa.Integer(), nullable=False, server_default="0"),
    )
