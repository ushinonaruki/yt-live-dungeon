import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import enemy_spawn, nickname_generator, stat_generator
from app.core.enemy_spawn import ROLE_MASTER, ROLE_MINION
from app.models.run import Run, RunState
from app.repositories.adventurer_repository import AdventurerRepository
from app.repositories.enemy_repository import EnemyRepository
from app.repositories.log_repository import LogRepository
from app.repositories.nickname_repository import NicknameRepository
from app.repositories.pending_join_repository import PendingJoinRepository
from app.repositories.run_repository import RunRepository


class NoEnemiesError(Exception):
    pass


class FloorService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.run_repo = RunRepository(db)
        self.adventurer_repo = AdventurerRepository(db)
        self.enemy_repo = EnemyRepository(db)
        self.nickname_repo = NicknameRepository(db)
        self.pending_join_repo = PendingJoinRepository(db)
        self.log_repo = LogRepository(db)

    async def start_floor(self, run: Run) -> dict:
        new_floor = run.current_floor + 1
        now = datetime.now(timezone.utc)

        pending_joins = await self.pending_join_repo.list_by_run(run.id)
        joining = pending_joins[:9]

        words = await self.nickname_repo.list_all()
        templates = await self.enemy_repo.list_templates()
        if not templates:
            raise NoEnemiesError

        # slot 1 = ひのきのフタ固定。自由枠は slot 2〜9 の 8 枠。
        initial_item = await self.adventurer_repo.find_item_by_spell_name(
            "hinokinofuta"
        )

        # 冒険者生成
        adventurers = []
        for pj in joining:
            stats = stat_generator.generate()
            nickname = nickname_generator.generate(words)
            adv = await self.adventurer_repo.create(
                run_id=run.id,
                youtube_id=pj.youtube_id,
                nickname=nickname,
                stats=stats,
                floor=new_floor,
                joined_at=now,
            )
            if initial_item:
                await self.adventurer_repo.assign_item(
                    adventurer_id=adv.id,
                    item_id=initial_item.id,
                    floor=new_floor,
                )
            adventurers.append(adv)

        await self.pending_join_repo.clear_by_run(run.id)

        # 敵生成
        specs = enemy_spawn.spawn(templates, new_floor)
        enemies: list[tuple] = []
        for spec in specs:
            e = await self.enemy_repo.create_run_enemy(
                run_id=run.id,
                spec=spec,
                floor=new_floor,
            )
            enemies.append((e, spec))

        await self.run_repo.begin_floor(run, new_floor)

        master_specs = [(e, s) for e, s in enemies if s.role == ROLE_MASTER]
        minion_specs = [(e, s) for e, s in enemies if s.role == ROLE_MINION]

        await self.log_repo.add(
            run_id=run.id,
            event_type="floor_start",
            body={
                "floor": new_floor,
                "adventurer_count": len(adventurers),
                "adventurers": [
                    {"youtube_id": a.youtube_id, "nickname": a.nickname, "hp": a.max_hp}
                    for a in adventurers
                ],
                "enemy_count": len(enemies),
                "master_count": len(master_specs),
                "minion_count": len(minion_specs),
                "enemies": [
                    {
                        "run_enemy_id": str(e.id),
                        "position": s.position,
                        "display_name": s.display_name,
                        "role": s.role,
                        "hp": s.max_hp,
                        "barrier": s.barrier,
                    }
                    for e, s in enemies
                ],
            },
        )

        for e, spec in master_specs:
            await self.log_repo.add(
                run_id=run.id,
                event_type="enemy_greeting",
                body={
                    "floor": new_floor,
                    "run_enemy_id": str(e.id),
                    "role": spec.role,
                    "display_name": spec.display_name,
                    "greeting": spec.greeting_action,
                },
            )

        if minion_specs:
            await self.log_repo.add(
                run_id=run.id,
                event_type="minion_deployed",
                body={
                    "floor": new_floor,
                    "minion_count": len(minion_specs),
                    "minions": [
                        {
                            "run_enemy_id": str(e.id),
                            "position": s.position,
                            "role": s.role,
                            "display_name": s.display_name,
                            "hp": s.max_hp,
                            "barrier": s.barrier,
                        }
                        for e, s in minion_specs
                    ],
                },
            )

        await self.db.commit()

        return {
            "run_id": run.id,
            "floor": new_floor,
            "adventurer_count": len(adventurers),
            "enemy_count": len(enemies),
        }
