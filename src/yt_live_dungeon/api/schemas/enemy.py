import uuid

from pydantic import BaseModel


class RunEnemyResponse(BaseModel):
    id: uuid.UUID
    enemy_key: str
    display_name: str
    role: str
    order_in_group: int
    max_hp: int
    hp: int
    max_mp: int
    mp: int
    attributes: dict[str, int]
    is_alive: bool
