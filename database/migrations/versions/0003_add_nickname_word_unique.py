"""add unique constraint to nickname_words.word

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_nickname_words_word", "nickname_words", ["word"])


def downgrade() -> None:
    op.drop_constraint("uq_nickname_words_word", "nickname_words", type_="unique")
