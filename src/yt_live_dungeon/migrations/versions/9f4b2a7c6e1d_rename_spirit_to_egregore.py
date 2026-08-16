"""rename spirit to egregore

Revision ID: 9f4b2a7c6e1d
Revises: 7c2a9e4f1b3d
Create Date: 2026-08-16 08:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '9f4b2a7c6e1d'
down_revision: Union[str, None] = '7c2a9e4f1b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# development seed's own egregore_key/display_name values that predate
# this rename (obsidian/.../キャラクター corpus never changes at the
# migration level, but pre-existing rows seeded under the old spirit_*
# keys must be updated in place -- not deleted/recreated -- so their id,
# blessing_item_id, and every FK pointing at them survive untouched).
# (old_key, new_key, old_display_name, new_display_name)
EGREGORE_KEY_RENAMES = [
    ('spirit_flame', 'egregore_flame', '炎の精霊(仮)', '炎のエグレゴア(仮)'),
    ('spirit_tide', 'egregore_tide', '潮の精霊(仮)', '潮のエグレゴア(仮)'),
]


def _rename_egregore_key(conn, from_key: str, to_key: str, to_display_name: str) -> None:
    """Renames one egregores.egregore_key value (and its display_name) in
    place via UPDATE -- never DELETE+INSERT -- so id, blessing_item_id,
    and every FK relationship pointing at this row are preserved exactly.

    A no-op if `from_key` doesn't exist (already renamed, or this
    environment never seeded it). Raises before touching anything if a
    *different* row already occupies `to_key`, since egregore_key is
    unique and that would either fail loudly mid-migration or, worse,
    silently collide.
    """
    from_row = conn.execute(
        sa.text('SELECT id FROM master.egregores WHERE egregore_key = :key'),
        {'key': from_key},
    ).fetchone()
    if from_row is None:
        return

    to_row = conn.execute(
        sa.text('SELECT id FROM master.egregores WHERE egregore_key = :key'),
        {'key': to_key},
    ).fetchone()
    if to_row is not None and to_row.id != from_row.id:
        raise RuntimeError(
            f'cannot rename egregores.egregore_key {from_key!r} to {to_key!r}: '
            f'a different row (id={to_row.id}) already uses {to_key!r}'
        )

    conn.execute(
        sa.text(
            'UPDATE master.egregores SET egregore_key = :to_key, display_name = :to_name '
            'WHERE egregore_key = :from_key'
        ),
        {'to_key': to_key, 'to_name': to_display_name, 'from_key': from_key},
    )


def upgrade() -> None:
    # Tables -- data-preserving rename, no drop/recreate.
    op.rename_table('spirits', 'egregores', schema='master')
    op.rename_table('spirit_item_pool_entries', 'egregore_item_pool_entries', schema='master')

    # Columns
    op.alter_column('egregores', 'spirit_key', new_column_name='egregore_key', schema='master')
    op.alter_column(
        'egregore_item_pool_entries', 'spirit_id', new_column_name='egregore_id', schema='master'
    )
    op.alter_column(
        'run_adventurers', 'spirit_id', new_column_name='egregore_id', schema='runtime'
    )
    op.alter_column('run_camps', 'spirit_id', new_column_name='egregore_id', schema='runtime')

    # Constraints -- renamed to match what the SQLAlchemy naming
    # convention now produces for the new table/column names, so a
    # future model-vs-DB diff never reports a spurious rename.
    op.execute(
        'ALTER TABLE master.egregores RENAME CONSTRAINT '
        'ck_spirits_representative_attribute_valid '
        'TO ck_egregores_representative_attribute_valid'
    )
    op.execute(
        'ALTER TABLE master.egregores RENAME CONSTRAINT '
        'fk_spirits_blessing_item_id_items TO fk_egregores_blessing_item_id_items'
    )
    op.execute('ALTER TABLE master.egregores RENAME CONSTRAINT pk_spirits TO pk_egregores')
    op.execute(
        'ALTER TABLE master.egregores RENAME CONSTRAINT '
        'uq_spirits_blessing_item_id TO uq_egregores_blessing_item_id'
    )
    op.execute(
        'ALTER TABLE master.egregores RENAME CONSTRAINT '
        'uq_spirits_spirit_key TO uq_egregores_egregore_key'
    )

    op.execute(
        'ALTER TABLE master.egregore_item_pool_entries RENAME CONSTRAINT '
        'fk_spirit_item_pool_entries_item_id_items '
        'TO fk_egregore_item_pool_entries_item_id_items'
    )
    op.execute(
        'ALTER TABLE master.egregore_item_pool_entries RENAME CONSTRAINT '
        'fk_spirit_item_pool_entries_spirit_id_spirits '
        'TO fk_egregore_item_pool_entries_egregore_id_egregores'
    )
    op.execute(
        'ALTER TABLE master.egregore_item_pool_entries RENAME CONSTRAINT '
        'pk_spirit_item_pool_entries TO pk_egregore_item_pool_entries'
    )

    op.execute(
        'ALTER TABLE runtime.run_adventurers RENAME CONSTRAINT '
        'fk_run_adventurers_spirit_id_spirits TO fk_run_adventurers_egregore_id_egregores'
    )
    op.execute(
        'ALTER TABLE runtime.run_camps RENAME CONSTRAINT '
        'fk_run_camps_spirit_id_spirits TO fk_run_camps_egregore_id_egregores'
    )

    # Data values -- rows seeded under the old spirit_* egregore_key
    # values (development seed's own former identifiers) are renamed in
    # place to match the new development seed, so a subsequent seed load
    # upserts onto the existing row instead of inserting a duplicate.
    conn = op.get_bind()
    for old_key, new_key, _old_name, new_name in EGREGORE_KEY_RENAMES:
        _rename_egregore_key(conn, old_key, new_key, new_name)


def downgrade() -> None:
    conn = op.get_bind()
    for old_key, new_key, old_name, _new_name in EGREGORE_KEY_RENAMES:
        _rename_egregore_key(conn, new_key, old_key, old_name)

    op.execute(
        'ALTER TABLE runtime.run_camps RENAME CONSTRAINT '
        'fk_run_camps_egregore_id_egregores TO fk_run_camps_spirit_id_spirits'
    )
    op.execute(
        'ALTER TABLE runtime.run_adventurers RENAME CONSTRAINT '
        'fk_run_adventurers_egregore_id_egregores TO fk_run_adventurers_spirit_id_spirits'
    )

    op.execute(
        'ALTER TABLE master.egregore_item_pool_entries RENAME CONSTRAINT '
        'pk_egregore_item_pool_entries TO pk_spirit_item_pool_entries'
    )
    op.execute(
        'ALTER TABLE master.egregore_item_pool_entries RENAME CONSTRAINT '
        'fk_egregore_item_pool_entries_egregore_id_egregores '
        'TO fk_spirit_item_pool_entries_spirit_id_spirits'
    )
    op.execute(
        'ALTER TABLE master.egregore_item_pool_entries RENAME CONSTRAINT '
        'fk_egregore_item_pool_entries_item_id_items '
        'TO fk_spirit_item_pool_entries_item_id_items'
    )

    op.execute(
        'ALTER TABLE master.egregores RENAME CONSTRAINT '
        'uq_egregores_egregore_key TO uq_spirits_spirit_key'
    )
    op.execute(
        'ALTER TABLE master.egregores RENAME CONSTRAINT '
        'uq_egregores_blessing_item_id TO uq_spirits_blessing_item_id'
    )
    op.execute('ALTER TABLE master.egregores RENAME CONSTRAINT pk_egregores TO pk_spirits')
    op.execute(
        'ALTER TABLE master.egregores RENAME CONSTRAINT '
        'fk_egregores_blessing_item_id_items TO fk_spirits_blessing_item_id_items'
    )
    op.execute(
        'ALTER TABLE master.egregores RENAME CONSTRAINT '
        'ck_egregores_representative_attribute_valid '
        'TO ck_spirits_representative_attribute_valid'
    )

    op.alter_column('run_camps', 'egregore_id', new_column_name='spirit_id', schema='runtime')
    op.alter_column(
        'run_adventurers', 'egregore_id', new_column_name='spirit_id', schema='runtime'
    )
    op.alter_column(
        'egregore_item_pool_entries', 'egregore_id', new_column_name='spirit_id', schema='master'
    )
    op.alter_column('egregores', 'egregore_key', new_column_name='spirit_key', schema='master')

    op.rename_table('egregore_item_pool_entries', 'spirit_item_pool_entries', schema='master')
    op.rename_table('egregores', 'spirits', schema='master')
