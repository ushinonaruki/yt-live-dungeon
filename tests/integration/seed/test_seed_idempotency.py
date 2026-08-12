import yaml
from sqlalchemy import func, select

from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Enemy,
    EnemySpell,
    Item,
    Spell,
    Spirit,
    SpiritItemPoolEntry,
)
from yt_live_dungeon.persistence.seed.load import SEED_DIR, load_seed

DEVELOPMENT_SEED = yaml.safe_load((SEED_DIR / "development.yaml").read_text(encoding="utf-8"))

SEEDED_MODELS = {
    "spells": Spell,
    "items": Item,
    "spirits": Spirit,
    "spirit_item_pool_entries": SpiritItemPoolEntry,
    "enemies": Enemy,
    "enemy_spells": EnemySpell,
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


async def test_each_active_spirit_has_at_least_two_pool_items():
    await _load_development_seed()

    async with async_session_factory() as session:
        active_spirits = (
            await session.execute(select(Spirit).where(Spirit.is_active.is_(True)))
        ).scalars().all()

        for spirit in active_spirits:
            pool_count = (
                await session.execute(
                    select(func.count())
                    .select_from(SpiritItemPoolEntry)
                    .where(SpiritItemPoolEntry.spirit_id == spirit.id)
                )
            ).scalar_one()
            assert pool_count >= 2, f"{spirit.spirit_key} has fewer than 2 pool items"


async def test_blessing_item_not_in_its_own_pool():
    await _load_development_seed()

    async with async_session_factory() as session:
        spirits = (await session.execute(select(Spirit))).scalars().all()

        for spirit in spirits:
            in_pool = (
                await session.execute(
                    select(func.count())
                    .select_from(SpiritItemPoolEntry)
                    .where(
                        SpiritItemPoolEntry.spirit_id == spirit.id,
                        SpiritItemPoolEntry.item_id == spirit.blessing_item_id,
                    )
                )
            ).scalar_one()
            assert in_pool == 0, f"{spirit.spirit_key}'s blessing item leaked into its own pool"
