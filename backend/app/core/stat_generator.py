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

    faith: int


ADVENTURER_COMMON_HP = 255


def _generate_6stats_sum72() -> list[int]:
    """[1, 20] の範囲で合計 72 になる 6 値をランダムに生成する。

    y_i = x_i - 1 (0 <= y_i <= 19) と変換し、合計 66 を 6 枠に分配する。
    各ステップで lo/hi を絞り込むことで必ず有効な結果が得られる。
    """
    n = 6
    max_y = 19  # 20 - 1
    target_y = 66  # 72 - 6

    parts: list[int] = []
    remaining = target_y
    for k in range(n - 1):
        lo = max(0, remaining - max_y * (n - k - 1))
        hi = min(max_y, remaining)
        v = random.randint(lo, hi)
        parts.append(v)
        remaining -= v
    parts.append(remaining)

    vals = [p + 1 for p in parts]
    random.shuffle(vals)
    return vals


def generate(faith: int = 0) -> AdventurerStats:
    vals = _generate_6stats_sum72()
    return AdventurerStats(
        hp=ADVENTURER_COMMON_HP,
        max_hp=ADVENTURER_COMMON_HP,
        str_val=vals[0],
        dex_val=vals[1],
        con_val=vals[2],
        int_val=vals[3],
        wis_val=vals[4],
        cha_val=vals[5],
        attr_red=0,
        attr_blue=0,
        attr_yellow=0,
        attr_green=0,
        attr_purple=0,
        attr_orange=0,
        faith=faith,
    )
