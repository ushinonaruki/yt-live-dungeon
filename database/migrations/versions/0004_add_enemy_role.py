"""add role column to run_enemies

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "run_enemies",
        sa.Column(
            "role",
            sa.String(16),
            nullable=False,
            server_default="master",
        ),
    )


def downgrade() -> None:
    op.drop_column("run_enemies", "role")
