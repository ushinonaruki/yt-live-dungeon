from yt_live_dungeon.domain.random_source import RandomSource


def draw_group_id(group_ids: list[int], random_source: RandomSource) -> int:
    """Uniform, with-replacement draw of one group id from `group_ids`.

    Per obsidian/YTL100ダンジョン/ダンジョン/マスターとミニオン.md section 4:
    no per-floor candidate restriction, no floor/group weighting, past
    groups are never excluded, and the same group may be drawn again
    immediately or repeatedly within one run. `group_ids` must already be
    in a stable, deterministic order (e.g. sorted by id) before this is
    called -- this function does not sort, so callers control
    reproducibility from the seed alone rather than incidental DB row
    order.
    """
    return random_source.sample(group_ids, 1)[0]
