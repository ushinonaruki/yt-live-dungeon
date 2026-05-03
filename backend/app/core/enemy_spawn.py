import math
import random
from dataclasses import dataclass, field
from typing import Literal

from app.models.enemy import Enemy

ROLE_MASTER: Literal["master"] = "master"
ROLE_MINION: Literal["minion"] = "minion"

EnemyRole = Literal["master", "minion"]


@dataclass
class EnemySpawnSpec:
    enemy_id: int
    display_name: str
    hp: int
    max_hp: int
    position: int
    role: EnemyRole
    greeting_action: dict = field(default_factory=dict)


def floor_hp_multiplier(floor: int) -> float:
    """10階ごとに x1.5 ずつ増加するHP倍率を返す。1〜9階は x1.0。"""
    tier = (floor - 1) // 10
    return 1.5**tier


def spawn(templates: list[Enemy], floor: int) -> list[EnemySpawnSpec]:
    """マスター1体 + ミニオン0〜8体を生成する。HPは base_hp × floor_hp_multiplier。"""
    if not templates:
        raise ValueError("No enemy templates available")

    multiplier = floor_hp_multiplier(floor)
    specs = []

    master_template = random.choice(templates)
    hp = math.floor(master_template.base_hp * multiplier)
    specs.append(
        EnemySpawnSpec(
            enemy_id=master_template.id,
            display_name=master_template.display_name,
            hp=hp,
            max_hp=hp,
            position=1,
            role=ROLE_MASTER,
            greeting_action=master_template.greeting_action or {},
        )
    )

    minion_count = random.randint(0, 8)
    for i in range(minion_count):
        t = random.choice(templates)
        hp = math.floor(t.base_hp * multiplier)
        specs.append(
            EnemySpawnSpec(
                enemy_id=t.id,
                display_name=t.display_name,
                hp=hp,
                max_hp=hp,
                position=i + 2,
                role=ROLE_MINION,
                greeting_action=t.greeting_action or {},
            )
        )

    return specs
