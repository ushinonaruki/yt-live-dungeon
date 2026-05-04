from dataclasses import dataclass

from app.core.stat_generator import AdventurerStats


@dataclass(frozen=True)
class AbilityCoeffs:
    str_coeff: int
    dex_coeff: int
    con_coeff: int
    int_coeff: int
    wis_coeff: int
    cha_coeff: int


def calculate_base_value(stats: AdventurerStats, coeffs: AbilityCoeffs) -> int:
    """呪文共通の基礎効果量を計算する。

    ability_power = 各能力値 * 対応係数の総和
    base_value = max(0, ability_power // 100)
    """
    ability_power = (
        stats.str_val * coeffs.str_coeff
        + stats.dex_val * coeffs.dex_coeff
        + stats.con_val * coeffs.con_coeff
        + stats.int_val * coeffs.int_coeff
        + stats.wis_val * coeffs.wis_coeff
        + stats.cha_val * coeffs.cha_coeff
    )
    return max(0, ability_power // 100)


# ひのきのフタ呪文の能力係数（全能力値 coeff=10）
HINOKINOFUTA_COEFFS = AbilityCoeffs(
    str_coeff=10,
    dex_coeff=10,
    con_coeff=10,
    int_coeff=10,
    wis_coeff=10,
    cha_coeff=10,
)


def calculate_hinokinofuta_damage(stats: AdventurerStats) -> int:
    """effect_id: damage_hinokinofuta の最小ダメージ計算。

    現時点では base_value をそのまま無属性ダメージとして返す。
    damage=0 でも攻撃はヒット扱い（将来の追加効果を考慮）。
    """
    return calculate_base_value(stats, HINOKINOFUTA_COEFFS)
