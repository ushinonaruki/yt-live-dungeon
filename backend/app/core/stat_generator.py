import random
from dataclasses import dataclass


@dataclass
class AdventurerStats:
    hp: int
    max_hp: int
    str_val: int
    dex_val: int
    con_val: int
    int_val: int
    wis_val: int
    cha_val: int
    attr_red: int
    attr_blue: int
    attr_yellow: int
    attr_green: int
    attr_purple: int
    attr_orange: int
    attr_indigo: int


ADVENTURER_COMMON_HP = 60


def generate() -> AdventurerStats:
    return AdventurerStats(
        hp=ADVENTURER_COMMON_HP,
        max_hp=ADVENTURER_COMMON_HP,
        str_val=random.randint(5, 15),
        dex_val=random.randint(5, 15),
        con_val=random.randint(5, 15),
        int_val=random.randint(5, 15),
        wis_val=random.randint(5, 15),
        cha_val=random.randint(5, 15),
        attr_red=random.randint(0, 3),
        attr_blue=random.randint(0, 3),
        attr_yellow=random.randint(0, 3),
        attr_green=random.randint(0, 3),
        attr_purple=random.randint(0, 3),
        attr_orange=random.randint(0, 3),
        attr_indigo=random.randint(0, 3),
    )
