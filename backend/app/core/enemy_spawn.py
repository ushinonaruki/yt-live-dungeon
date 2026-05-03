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
    greeting_action: dict = field(default_factory=dict)


ENEMY_COMMON_HP = 70


def spawn(templates: list[Enemy], floor: int) -> list[EnemySpawnSpec]:
    """全敵共通 HP、フロアごとの耐久差は barrier のみで表現する。"""
    if not templates:
        raise ValueError("No enemy templates available")

    count = random.randint(1, 5)
    hp = ENEMY_COMMON_HP
    specs = []
    for i in range(count):
        t = random.choice(templates)
        barrier = t.base_barrier + floor * 10
        specs.append(
            EnemySpawnSpec(
                enemy_id=t.id,
                display_name=t.display_name,
                hp=hp,
                max_hp=hp,
                barrier=barrier,
                position=i + 1,
                greeting_action=t.greeting_action or {},
            )
        )
    return specs
