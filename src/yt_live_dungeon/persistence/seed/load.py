import asyncio
import sys
from pathlib import Path

import yaml
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Enemy,
    EnemySpell,
    Item,
    Spell,
    Spirit,
    SpiritItemPoolEntry,
)

SEED_DIR = Path(__file__).parent


async def _upsert_spells(session: AsyncSession, spells: list[dict]) -> dict[str, int]:
    ids: dict[str, int] = {}
    for spell in spells:
        stmt = (
            pg_insert(Spell)
            .values(**spell)
            .on_conflict_do_update(
                index_elements=[Spell.command],
                set_={key: value for key, value in spell.items() if key != "command"},
            )
            .returning(Spell.id)
        )
        result = await session.execute(stmt)
        ids[spell["command"]] = result.scalar_one()
    return ids


async def _upsert_items(
    session: AsyncSession, items: list[dict], spell_ids: dict[str, int]
) -> dict[str, int]:
    ids: dict[str, int] = {}
    for item in items:
        payload = {
            "item_key": item["item_key"],
            "display_name": item["display_name"],
            "attribute": item["attribute"],
            "granted_spell_id": spell_ids[item["granted_spell_command"]],
            "base_stat_modifiers": item.get("base_stat_modifiers", {}),
            "per_level_stat_modifiers": item.get("per_level_stat_modifiers", {}),
            "break_effects": item.get("break_effects", []),
            "is_active": item.get("is_active", True),
        }
        stmt = (
            pg_insert(Item)
            .values(**payload)
            .on_conflict_do_update(
                index_elements=[Item.item_key],
                set_={key: value for key, value in payload.items() if key != "item_key"},
            )
            .returning(Item.id)
        )
        result = await session.execute(stmt)
        ids[item["item_key"]] = result.scalar_one()
    return ids


async def _upsert_spirits(
    session: AsyncSession, spirits: list[dict], item_ids: dict[str, int]
) -> None:
    for spirit in spirits:
        payload = {
            "spirit_key": spirit["spirit_key"],
            "display_name": spirit["display_name"],
            "representative_attribute": spirit["representative_attribute"],
            "blessing_item_id": item_ids[spirit["blessing_item_key"]],
            "is_active": spirit.get("is_active", True),
        }
        stmt = (
            pg_insert(Spirit)
            .values(**payload)
            .on_conflict_do_update(
                index_elements=[Spirit.spirit_key],
                set_={key: value for key, value in payload.items() if key != "spirit_key"},
            )
            .returning(Spirit.id)
        )
        result = await session.execute(stmt)
        spirit_id = result.scalar_one()

        for pool_item_key in spirit.get("pool_item_keys", []):
            entry_stmt = (
                pg_insert(SpiritItemPoolEntry)
                .values(spirit_id=spirit_id, item_id=item_ids[pool_item_key])
                .on_conflict_do_nothing(
                    index_elements=[
                        SpiritItemPoolEntry.spirit_id,
                        SpiritItemPoolEntry.item_id,
                    ]
                )
            )
            await session.execute(entry_stmt)


async def _upsert_enemies(
    session: AsyncSession, enemies: list[dict], spell_ids: dict[str, int]
) -> None:
    for enemy in enemies:
        payload = {
            "enemy_key": enemy["enemy_key"],
            "display_name": enemy["display_name"],
            "base_max_hp": enemy["base_max_hp"],
            "base_max_mp": enemy["base_max_mp"],
            "base_attributes": enemy.get("base_attributes", {}),
            "weak_attribute": enemy.get("weak_attribute"),
            "break_max": enemy["break_max"],
            "ai_policy_key": enemy.get("ai_policy_key", "random_v1"),
            "ai_policy_config": enemy.get("ai_policy_config", {}),
            "is_active": enemy.get("is_active", True),
        }
        stmt = (
            pg_insert(Enemy)
            .values(**payload)
            .on_conflict_do_update(
                index_elements=[Enemy.enemy_key],
                set_={key: value for key, value in payload.items() if key != "enemy_key"},
            )
            .returning(Enemy.id)
        )
        result = await session.execute(stmt)
        enemy_id = result.scalar_one()

        for spell_command in enemy.get("spell_commands", []):
            entry_stmt = (
                pg_insert(EnemySpell)
                .values(enemy_id=enemy_id, spell_id=spell_ids[spell_command])
                .on_conflict_do_nothing(
                    index_elements=[EnemySpell.enemy_id, EnemySpell.spell_id]
                )
            )
            await session.execute(entry_stmt)


async def load_seed(session: AsyncSession, data: dict) -> None:
    spell_ids = await _upsert_spells(session, data.get("spells", []))
    item_ids = await _upsert_items(session, data.get("items", []), spell_ids)
    await _upsert_spirits(session, data.get("spirits", []), item_ids)
    await _upsert_enemies(session, data.get("enemies", []), spell_ids)


async def main(seed_name: str) -> None:
    seed_path = SEED_DIR / f"{seed_name}.yaml"
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))

    async with async_session_factory() as session:
        async with session.begin():
            await load_seed(session, data)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m yt_live_dungeon.persistence.seed.load <seed_name>")
    asyncio.run(main(sys.argv[1]))
