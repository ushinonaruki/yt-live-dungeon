import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.spell_effects import calculate_hinokinofuta_damage
from app.core.stat_generator import AdventurerStats
from app.models.run_adventurer import RunAdventurer
from app.repositories.enemy_repository import EnemyRepository
from app.repositories.log_repository import LogRepository


@dataclass
class HinokinofutaResult:
    target_enemy_id: uuid.UUID
    target_display_name: str
    damage: int
    hp_before: int
    hp_after: int
    enemy_defeated: bool


class NoAliveEnemyError(Exception):
    pass


def _stats_from_adventurer(adv: RunAdventurer) -> AdventurerStats:
    return AdventurerStats(
        hp=adv.hp,
        max_hp=adv.max_hp,
        str_val=adv.str_val,
        dex_val=adv.dex_val,
        con_val=adv.con_val,
        int_val=adv.int_val,
        wis_val=adv.wis_val,
        cha_val=adv.cha_val,
        attr_red=adv.attr_red,
        attr_blue=adv.attr_blue,
        attr_yellow=adv.attr_yellow,
        attr_green=adv.attr_green,
        attr_purple=adv.attr_purple,
        attr_orange=adv.attr_orange,
        faith=adv.faith,
    )


class BattleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.enemy_repo = EnemyRepository(db)
        self.log_repo = LogRepository(db)

    async def use_hinokinofuta(
        self,
        run_id: uuid.UUID,
        adventurer: RunAdventurer,
    ) -> HinokinofutaResult:
        """ひのきのフタ攻撃処理。生存敵からランダムに1体を選びダメージを与える。"""
        alive_enemies = await self.enemy_repo.list_alive_by_run(run_id)
        if not alive_enemies:
            await self.log_repo.add(
                run_id=run_id,
                event_type="spell_no_target",
                body={
                    "spell": "hinokinofuta",
                    "spell_display_name": "ひのきのフタ",
                    "adventurer_id": str(adventurer.id),
                    "adventurer_nickname": adventurer.nickname,
                },
            )
            raise NoAliveEnemyError("No alive enemies to target")

        target_enemy, target_display_name = random.choice(alive_enemies)

        stats = _stats_from_adventurer(adventurer)
        damage = calculate_hinokinofuta_damage(stats)
        hp_before = target_enemy.hp
        hp_after = max(0, hp_before - damage)
        enemy_defeated = hp_after <= 0

        now = datetime.now(timezone.utc)
        if enemy_defeated:
            await self.enemy_repo.mark_defeated(target_enemy, now)
        else:
            await self.enemy_repo.update_hp(target_enemy, hp_after)

        await self.log_repo.add(
            run_id=run_id,
            event_type="spell_damage",
            body={
                "spell": "hinokinofuta",
                "spell_display_name": "ひのきのフタ",
                "adventurer_id": str(adventurer.id),
                "adventurer_nickname": adventurer.nickname,
                "enemy_id": str(target_enemy.id),
                "enemy_display_name": target_display_name,
                "damage": damage,
                "enemy_hp_before": hp_before,
                "enemy_hp_after": hp_after,
                "enemy_defeated": enemy_defeated,
            },
        )

        if enemy_defeated:
            await self.log_repo.add(
                run_id=run_id,
                event_type="enemy_defeated",
                body={
                    "spell": "hinokinofuta",
                    "enemy_id": str(target_enemy.id),
                    "enemy_display_name": target_display_name,
                    "adventurer_id": str(adventurer.id),
                    "adventurer_nickname": adventurer.nickname,
                },
            )

        return HinokinofutaResult(
            target_enemy_id=target_enemy.id,
            target_display_name=target_display_name,
            damage=damage,
            hp_before=hp_before,
            hp_after=hp_after,
            enemy_defeated=enemy_defeated,
        )
