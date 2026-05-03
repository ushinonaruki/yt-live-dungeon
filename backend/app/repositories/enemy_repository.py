import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enemy_spawn import EnemySpawnSpec
from app.models.enemy import Enemy
from app.models.run_enemy import RunEnemy


class EnemyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_templates(self) -> list[Enemy]:
        result = await self.db.execute(select(Enemy).order_by(Enemy.id))
        return list(result.scalars().all())

    async def create_run_enemy(
        self, run_id: uuid.UUID, spec: EnemySpawnSpec, floor: int
    ) -> RunEnemy:
        enemy = RunEnemy(
            run_id=run_id,
            enemy_id=spec.enemy_id,
            floor=floor,
            hp=spec.hp,
            max_hp=spec.max_hp,
            barrier=spec.barrier,
            position=spec.position,
        )
        self.db.add(enemy)
        await self.db.flush()
        return enemy

    async def list_by_run(self, run_id: uuid.UUID) -> list[tuple[RunEnemy, str]]:
        """RunEnemy と敵の display_name をセットで返す。"""
        rows = await self.db.execute(
            select(RunEnemy, Enemy.display_name)
            .join(Enemy, RunEnemy.enemy_id == Enemy.id)
            .where(RunEnemy.run_id == run_id)
            .order_by(RunEnemy.position)
        )
        return [(row[0], row[1]) for row in rows.all()]
