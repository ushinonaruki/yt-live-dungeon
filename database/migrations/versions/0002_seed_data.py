"""seed data

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO spells (name, display_name, formula, cooldown_seconds) VALUES
          ('hinokinofuta', 'ひのきのフタ', '{"type": "damage", "base": 3}', 3.0)
        ON CONFLICT (name) DO NOTHING
    """)

    op.execute("""
        INSERT INTO items (name, display_name, description, stat_mods, attribute_mods, passive_effects, unlocks_spell_id)
        SELECT 'ひのきのフタ', 'ひのきのフタ', '呪文「ひのきのフタ」を使えるようになる', '{}', '{}', '{}', id
        FROM spells WHERE name = 'hinokinofuta'
        ON CONFLICT (name) DO NOTHING
    """)

    op.execute("""
        INSERT INTO enemies (name, display_name, base_hp, base_barrier, special_actions, greeting_action) VALUES
          ('slime',  'スライム',   40, 0, '[]', '{"type": "speak", "text": "ぷるぷる…"}'),
          ('goblin', 'ゴブリン',   60, 0, '[]', '{"type": "speak", "text": "ガルルル！"}'),
          ('bat',    'コウモリ',   30, 0, '[]', '{"type": "speak", "text": "キキキ！"}')
        ON CONFLICT (name) DO NOTHING
    """)

    op.execute("""
        INSERT INTO nickname_words (word, part) VALUES
          ('勇敢な',   'adj'), ('謎の',       'adj'), ('伝説の',     'adj'),
          ('小さな',   'adj'), ('巨大な',     'adj'), ('無口な',     'adj'),
          ('陽気な',   'adj'), ('臆病な',     'adj'), ('猛烈な',     'adj'),
          ('静かな',   'adj'),
          ('戦士',   'noun'), ('魔法使い', 'noun'), ('盗賊',     'noun'),
          ('僧侶',   'noun'), ('賢者',     'noun'), ('騎士',     'noun'),
          ('忍者',   'noun'), ('剣士',     'noun'), ('弓使い',   'noun'),
          ('錬金術師', 'noun')
    """)


def downgrade() -> None:
    op.execute("DELETE FROM items WHERE name = 'ひのきのフタ'")
    op.execute("DELETE FROM spells WHERE name = 'hinokinofuta'")
    op.execute("DELETE FROM enemies WHERE name IN ('slime', 'goblin', 'bat')")
    op.execute("""
        DELETE FROM nickname_words WHERE word IN (
          '勇敢な', '謎の', '伝説の', '小さな', '巨大な', '無口な',
          '陽気な', '臆病な', '猛烈な', '静かな',
          '戦士', '魔法使い', '盗賊', '僧侶', '賢者',
          '騎士', '忍者', '剣士', '弓使い', '錬金術師'
        )
    """)
