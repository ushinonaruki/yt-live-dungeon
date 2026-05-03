"""spec alignment: add oshi_name to pending_joins and faith to run_adventurers

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "run_pending_joins",
        sa.Column("oshi_name", sa.String(256), nullable=True),
    )

    op.add_column(
        "run_adventurers",
        sa.Column(
            "faith",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("run_adventurers", "faith")
    op.drop_column("run_pending_joins", "oshi_name")
