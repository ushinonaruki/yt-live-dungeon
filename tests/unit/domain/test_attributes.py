from yt_live_dungeon.domain.attributes import STAT_MODIFIER_KEYS


def test_stat_modifier_keys_excludes_max_mp():
    """Per obsidian/.../キャラクター/ステータス.md section 5: max MP is
    fixed at 100 for every combatant, so it is never a valid item stat
    modifier target."""
    assert "max_mp" not in STAT_MODIFIER_KEYS
