"""drop attr_indigo from run_adventurers (not in spec)

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("run_adventurers", "attr_indigo")


def downgrade() -> None:
    op.add_column(
        "run_adventurers",
        sa.Column("attr_indigo", sa.Integer(), nullable=False, server_default="0"),
    )
