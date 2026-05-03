import random
from dataclasses import dataclass, field

from app.models.enemy import Enemy


@dataclass
class EnemySpawnSpec:
    enemy_id: int
    display_name: str
    hp: int
    max_hp: int
    barrier: int
    position: int
    role: str  # "master" or "minion"
    greeting_action: dict = field(default_factory=dict)


ENEMY_COMMON_HP = 70


def spawn(templates: list[Enemy], floor: int) -> list[EnemySpawnSpec]:
    """マスター1体 + ミニオン0〜8体を生成する。全敵共通 HP、耐久差は barrier のみ。"""
    if not templates:
        raise ValueError("No enemy templates available")

    hp = ENEMY_COMMON_HP
    specs = []

    master_template = random.choice(templates)
    specs.append(
        EnemySpawnSpec(
            enemy_id=master_template.id,
            display_name=master_template.display_name,
            hp=hp,
            max_hp=hp,
            barrier=master_template.base_barrier + floor * 10,
            position=1,
            role="master",
            greeting_action=master_template.greeting_action or {},
        )
    )

    minion_count = random.randint(0, 8)
    for i in range(minion_count):
        t = random.choice(templates)
        specs.append(
            EnemySpawnSpec(
                enemy_id=t.id,
                display_name=t.display_name,
                hp=hp,
                max_hp=hp,
                barrier=t.base_barrier + floor * 10,
                position=i + 2,
                role="minion",
                greeting_action=t.greeting_action or {},
            )
        )

    return specs
