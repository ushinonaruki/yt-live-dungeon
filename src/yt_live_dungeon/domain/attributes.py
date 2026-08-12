ATTRIBUTE_CODES: tuple[str, ...] = (
    "RR",
    "YR",
    "YY",
    "GY",
    "GG",
    "BG",
    "BB",
    "PB",
    "PP",
    "RP",
)

# Lowercase attribute keys as used inside item stat-modifier JSON payloads
# (base_stat_modifiers / per_level_stat_modifiers), distinct from the
# uppercase ATTRIBUTE_CODES used for the `attribute` column values.
ATTRIBUTE_MODIFIER_KEYS: tuple[str, ...] = (
    "rr",
    "yr",
    "yy",
    "gy",
    "gg",
    "bg",
    "bb",
    "pb",
    "pp",
    "rp",
)

STAT_MODIFIER_KEYS: tuple[str, ...] = ("max_hp", "max_mp") + ATTRIBUTE_MODIFIER_KEYS
