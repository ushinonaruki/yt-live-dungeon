import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.stat_generator import AdventurerStats
from app.models.item import Item
from app.models.run_adventurer import RunAdventurer
from app.models.run_adventurer_item import RunAdventurerItem
from app.models.spell import Spell


class AdventurerRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        run_id: uuid.UUID,
        youtube_id: str,
        nickname: str,
        stats: AdventurerStats,
        floor: int,
        joined_at: datetime,
    ) -> RunAdventurer:
        adv = RunAdventurer(
            run_id=run_id,
            youtube_id=youtube_id,
            nickname=nickname,
            hp=stats.hp,
            max_hp=stats.max_hp,
            str_val=stats.str_val,
            dex_val=stats.dex_val,
            con_val=stats.con_val,
            int_val=stats.int_val,
            wis_val=stats.wis_val,
            cha_val=stats.cha_val,
            attr_red=stats.attr_red,
            attr_blue=stats.attr_blue,
            attr_yellow=stats.attr_yellow,
            attr_green=stats.attr_green,
            attr_purple=stats.attr_purple,
            attr_orange=stats.attr_orange,
            attr_indigo=stats.attr_indigo,
            joined_floor=floor,
            joined_at=joined_at,
        )
        self.db.add(adv)
        await self.db.flush()
        return adv

    async def assign_item(
        self, adventurer_id: uuid.UUID, item_id: int, floor: int
    ) -> RunAdventurerItem:
        record = RunAdventurerItem(
            run_adventurer_id=adventurer_id,
            item_id=item_id,
            slot=1,
            acquired_floor=floor,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def list_by_run(self, run_id: uuid.UUID) -> list[RunAdventurer]:
        result = await self.db.execute(
            select(RunAdventurer)
            .where(RunAdventurer.run_id == run_id)
            .order_by(RunAdventurer.joined_at)
        )
        return list(result.scalars().all())

    async def find_item_by_spell_name(self, spell_name: str) -> Item | None:
        q = (
            select(Item)
            .join(Spell, Item.unlocks_spell_id == Spell.id)
            .where(Spell.name == spell_name)
        )
        return (await self.db.execute(q)).scalar_one_or_none()
