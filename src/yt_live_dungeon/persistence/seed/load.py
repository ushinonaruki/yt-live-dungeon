import asyncio
import sys
from pathlib import Path

import yaml
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.features.floor.group_validation import (
    GroupMemberSpec,
    validate_group_composition,
)
from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Egregore,
    EgregoreItemPoolEntry,
    Enemy,
    EnemyGroup,
    EnemyGroupMember,
    EnemySpell,
    Item,
    Spell,
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


async def _upsert_egregores(
    session: AsyncSession, egregores: list[dict], item_ids: dict[str, int]
) -> None:
    for egregore in egregores:
        payload = {
            "egregore_key": egregore["egregore_key"],
            "display_name": egregore["display_name"],
            "representative_attribute": egregore["representative_attribute"],
            "blessing_item_id": item_ids[egregore["blessing_item_key"]],
            "is_active": egregore.get("is_active", True),
        }
        stmt = (
            pg_insert(Egregore)
            .values(**payload)
            .on_conflict_do_update(
                index_elements=[Egregore.egregore_key],
                set_={key: value for key, value in payload.items() if key != "egregore_key"},
            )
            .returning(Egregore.id)
        )
        result = await session.execute(stmt)
        egregore_id = result.scalar_one()

        for pool_item_key in egregore.get("pool_item_keys", []):
            entry_stmt = (
                pg_insert(EgregoreItemPoolEntry)
                .values(egregore_id=egregore_id, item_id=item_ids[pool_item_key])
                .on_conflict_do_nothing(
                    index_elements=[
                        EgregoreItemPoolEntry.egregore_id,
                        EgregoreItemPoolEntry.item_id,
                    ]
                )
            )
            await session.execute(entry_stmt)


async def _upsert_enemies(
    session: AsyncSession, enemies: list[dict], spell_ids: dict[str, int]
) -> dict[str, int]:
    ids: dict[str, int] = {}
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
        ids[enemy["enemy_key"]] = enemy_id

        for spell_command in enemy.get("spell_commands", []):
            entry_stmt = (
                pg_insert(EnemySpell)
                .values(enemy_id=enemy_id, spell_id=spell_ids[spell_command])
                .on_conflict_do_nothing(
                    index_elements=[EnemySpell.enemy_id, EnemySpell.spell_id]
                )
            )
            await session.execute(entry_stmt)
    return ids


async def _upsert_enemy_groups(
    session: AsyncSession, groups: list[dict], enemy_ids: dict[str, int]
) -> None:
    for group in groups:
        members = group.get("members", [])
        validate_group_composition(
            [
                GroupMemberSpec(order_in_group=member["order_in_group"], role=member["role"])
                for member in members
            ]
        )

        payload = {
            "group_key": group["group_key"],
            "display_name": group["display_name"],
            "is_active": group.get("is_active", True),
        }
        stmt = (
            pg_insert(EnemyGroup)
            .values(**payload)
            .on_conflict_do_update(
                index_elements=[EnemyGroup.group_key],
                set_={key: value for key, value in payload.items() if key != "group_key"},
            )
            .returning(EnemyGroup.id)
        )
        result = await session.execute(stmt)
        group_id = result.scalar_one()

        for member in members:
            member_stmt = (
                pg_insert(EnemyGroupMember)
                .values(
                    group_id=group_id,
                    order_in_group=member["order_in_group"],
                    enemy_id=enemy_ids[member["enemy_key"]],
                    role=member["role"],
                )
                .on_conflict_do_update(
                    index_elements=[
                        EnemyGroupMember.group_id,
                        EnemyGroupMember.order_in_group,
                    ],
                    set_={
                        "enemy_id": enemy_ids[member["enemy_key"]],
                        "role": member["role"],
                    },
                )
            )
            await session.execute(member_stmt)


async def load_seed(session: AsyncSession, data: dict) -> None:
    spell_ids = await _upsert_spells(session, data.get("spells", []))
    item_ids = await _upsert_items(session, data.get("items", []), spell_ids)
    await _upsert_egregores(session, data.get("egregores", []), item_ids)
    enemy_ids = await _upsert_enemies(session, data.get("enemies", []), spell_ids)
    await _upsert_enemy_groups(session, data.get("enemy_groups", []), enemy_ids)


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
