import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enemy_spawn import ROLE_MASTER, ROLE_MINION, EnemySpawnSpec
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
            position=spec.position,
            role=spec.role,
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

    async def list_alive_by_run(self, run_id: uuid.UUID) -> list[tuple[RunEnemy, str]]:
        rows = await self.db.execute(
            select(RunEnemy, Enemy.display_name)
            .join(Enemy, RunEnemy.enemy_id == Enemy.id)
            .where(RunEnemy.run_id == run_id, RunEnemy.is_alive.is_(True))
            .order_by(RunEnemy.position)
        )
        return [(row[0], row[1]) for row in rows.all()]

    async def get_alive_master(self, run_id: uuid.UUID) -> tuple[RunEnemy, str] | None:
        row = await self.db.execute(
            select(RunEnemy, Enemy.display_name)
            .join(Enemy, RunEnemy.enemy_id == Enemy.id)
            .where(
                RunEnemy.run_id == run_id,
                RunEnemy.role == ROLE_MASTER,
                RunEnemy.is_alive.is_(True),
            )
        )
        result = row.first()
        if result is None:
            return None
        return (result[0], result[1])

    async def list_alive_minions(self, run_id: uuid.UUID) -> list[tuple[RunEnemy, str]]:
        rows = await self.db.execute(
            select(RunEnemy, Enemy.display_name)
            .join(Enemy, RunEnemy.enemy_id == Enemy.id)
            .where(
                RunEnemy.run_id == run_id,
                RunEnemy.role == ROLE_MINION,
                RunEnemy.is_alive.is_(True),
            )
            .order_by(RunEnemy.position)
        )
        return [(row[0], row[1]) for row in rows.all()]

    async def get_alive_by_id(
        self, run_id: uuid.UUID, run_enemy_id: uuid.UUID
    ) -> RunEnemy | None:
        result = await self.db.execute(
            select(RunEnemy).where(
                RunEnemy.run_id == run_id,
                RunEnemy.id == run_enemy_id,
                RunEnemy.is_alive.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def update_hp(self, enemy: RunEnemy, hp: int) -> RunEnemy:
        enemy.hp = hp
        await self.db.flush()
        return enemy

    async def mark_defeated(self, enemy: RunEnemy, defeated_at: datetime) -> RunEnemy:
        enemy.hp = 0
        enemy.is_alive = False
        enemy.died_at = defeated_at
        await self.db.flush()
        return enemy
