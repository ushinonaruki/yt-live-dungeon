import yaml
from sqlalchemy import func, select

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
from yt_live_dungeon.persistence.seed.load import SEED_DIR, load_seed

DEVELOPMENT_SEED = yaml.safe_load((SEED_DIR / "development.yaml").read_text(encoding="utf-8"))

SEEDED_MODELS = {
    "spells": Spell,
    "items": Item,
    "egregores": Egregore,
    "egregore_item_pool_entries": EgregoreItemPoolEntry,
    "enemies": Enemy,
    "enemy_spells": EnemySpell,
    "enemy_groups": EnemyGroup,
    "enemy_group_members": EnemyGroupMember,
}


async def _load_development_seed() -> None:
    async with async_session_factory() as session:
        async with session.begin():
            await load_seed(session, DEVELOPMENT_SEED)


async def _counts() -> dict[str, int]:
    async with async_session_factory() as session:
        return {
            name: (await session.execute(select(func.count()).select_from(model))).scalar_one()
            for name, model in SEEDED_MODELS.items()
        }


async def test_seed_is_idempotent():
    await _load_development_seed()
    counts_before = await _counts()

    await _load_development_seed()
    counts_after = await _counts()

    assert counts_after == counts_before


async def test_each_active_egregore_has_at_least_two_pool_items():
    await _load_development_seed()

    async with async_session_factory() as session:
        active_egregores = (
            await session.execute(select(Egregore).where(Egregore.is_active.is_(True)))
        ).scalars().all()

        for egregore in active_egregores:
            pool_count = (
                await session.execute(
                    select(func.count())
                    .select_from(EgregoreItemPoolEntry)
                    .where(EgregoreItemPoolEntry.egregore_id == egregore.id)
                )
            ).scalar_one()
            assert pool_count >= 2, f"{egregore.egregore_key} has fewer than 2 pool items"


def test_development_seed_items_carry_no_max_mp_modifier():
    """Per obsidian/.../アイテム/アイテム定義仕様.md section 7: max MP is
    fixed at 100 for every combatant, so no item's stat modifiers may
    include a "max_mp" key."""
    for item in DEVELOPMENT_SEED.get("items", []):
        assert "max_mp" not in item.get("base_stat_modifiers", {}), item["item_key"]
        assert "max_mp" not in item.get("per_level_stat_modifiers", {}), item["item_key"]


def test_development_seed_enemies_have_base_max_mp_of_100():
    for enemy in DEVELOPMENT_SEED.get("enemies", []):
        assert enemy["base_max_mp"] == 100, enemy["enemy_key"]


async def test_blessing_item_not_in_its_own_pool():
    await _load_development_seed()

    async with async_session_factory() as session:
        egregores = (await session.execute(select(Egregore))).scalars().all()

        for egregore in egregores:
            in_pool = (
                await session.execute(
                    select(func.count())
                    .select_from(EgregoreItemPoolEntry)
                    .where(
                        EgregoreItemPoolEntry.egregore_id == egregore.id,
                        EgregoreItemPoolEntry.item_id == egregore.blessing_item_id,
                    )
                )
            ).scalar_one()
            assert in_pool == 0, f"{egregore.egregore_key}'s blessing item leaked into its own pool"
