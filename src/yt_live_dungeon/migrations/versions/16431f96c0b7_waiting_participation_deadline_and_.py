"""waiting participation deadline and ready state

Revision ID: 16431f96c0b7
Revises: b195bebfaf29
Create Date: 2026-08-16 04:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '16431f96c0b7'
down_revision: Union[str, None] = 'b195bebfaf29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'runs',
        sa.Column('waiting_deadline_at', sa.DateTime(timezone=True), nullable=True),
        schema='runtime',
    )
    op.add_column(
        'run_adventurers',
        sa.Column('waiting_ready_at', sa.DateTime(timezone=True), nullable=True),
        schema='runtime',
    )


def downgrade() -> None:
    op.drop_column('run_adventurers', 'waiting_ready_at', schema='runtime')
    op.drop_column('runs', 'waiting_deadline_at', schema='runtime')
