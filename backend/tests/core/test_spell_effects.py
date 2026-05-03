import pytest

from app.core.spell_effects import (
    AbilityCoeffs,
    HINOKINOFUTA_COEFFS,
    calculate_base_value,
    calculate_hinokinofuta_damage,
)
from app.core.stat_generator import AdventurerStats


def _make_stats(
    str_val: int,
    dex_val: int,
    con_val: int,
    int_val: int,
    wis_val: int,
    cha_val: int,
) -> AdventurerStats:
    return AdventurerStats(
        hp=255,
        max_hp=255,
        str_val=str_val,
        dex_val=dex_val,
        con_val=con_val,
        int_val=int_val,
        wis_val=wis_val,
        cha_val=cha_val,
        attr_red=0,
        attr_blue=0,
        attr_yellow=0,
        attr_green=0,
        attr_purple=0,
        attr_orange=0,
        faith=0,
    )


class TestCalculateBaseValue:
    def test_sum72_coeff10_returns_7(self):
        # 仕様ケース: STR〜CHA 合計 72, coeff 全て 10
        # ability_power = 720, base_value = 720 // 100 = 7
        stats = _make_stats(12, 12, 12, 12, 12, 12)  # 合計 72
        coeffs = AbilityCoeffs(
            str_coeff=10,
            dex_coeff=10,
            con_coeff=10,
            int_coeff=10,
            wis_coeff=10,
            cha_coeff=10,
        )
        assert calculate_base_value(stats, coeffs) == 7

    def test_ability_power_below_100_returns_0(self):
        # ability_power < 100 => base_value = 0
        stats = _make_stats(1, 1, 1, 1, 1, 1)  # 合計 6
        coeffs = AbilityCoeffs(
            str_coeff=10,
            dex_coeff=10,
            con_coeff=10,
            int_coeff=10,
            wis_coeff=10,
            cha_coeff=10,
        )
        # ability_power = 60, base_value = max(0, 60 // 100) = 0
        assert calculate_base_value(stats, coeffs) == 0

    def test_ability_power_exactly_100_returns_1(self):
        # ability_power = 100 => base_value = 1
        stats = _make_stats(2, 2, 2, 2, 2, 0)
        coeffs = AbilityCoeffs(
            str_coeff=10,
            dex_coeff=10,
            con_coeff=10,
            int_coeff=10,
            wis_coeff=10,
            cha_coeff=10,
        )
        # ability_power = 100, base_value = 1
        assert calculate_base_value(stats, coeffs) == 1

    def test_zero_coeffs_returns_0(self):
        stats = _make_stats(20, 20, 20, 20, 20, 20)
        coeffs = AbilityCoeffs(
            str_coeff=0,
            dex_coeff=0,
            con_coeff=0,
            int_coeff=0,
            wis_coeff=0,
            cha_coeff=0,
        )
        assert calculate_base_value(stats, coeffs) == 0


class TestCalculateHinokinofutaDamage:
    def test_sum72_returns_7(self):
        # 仕様ケース: 合計 72 => 7 ダメージ
        stats = _make_stats(12, 12, 12, 12, 12, 12)
        assert calculate_hinokinofuta_damage(stats) == 7

    def test_uses_hinokinofuta_coeffs(self):
        # 係数が全て 10 であることを確認
        assert HINOKINOFUTA_COEFFS.str_coeff == 10
        assert HINOKINOFUTA_COEFFS.dex_coeff == 10
        assert HINOKINOFUTA_COEFFS.con_coeff == 10
        assert HINOKINOFUTA_COEFFS.int_coeff == 10
        assert HINOKINOFUTA_COEFFS.wis_coeff == 10
        assert HINOKINOFUTA_COEFFS.cha_coeff == 10

    def test_low_stats_returns_0(self):
        # 能力値が低い場合は 0 ダメージ (最低1ダメージは現時点では未適用)
        stats = _make_stats(1, 1, 1, 1, 1, 1)
        assert calculate_hinokinofuta_damage(stats) == 0

    def test_max_stats_returns_12(self):
        # 全能力値 20 (合計 120) => ability_power = 1200, base_value = 12
        stats = _make_stats(20, 20, 20, 20, 20, 20)
        assert calculate_hinokinofuta_damage(stats) == 12
