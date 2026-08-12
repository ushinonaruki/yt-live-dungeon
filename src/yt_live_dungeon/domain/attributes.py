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


def validate_attribute_dict(attributes: dict) -> None:
    """Rejects anything but exactly the 10 ATTRIBUTE_MODIFIER_KEYS with
    integer values -- no missing key, no extra key, no bool/float/str.
    Used at the application boundary for RunEnemy.attributes, which is
    an unconstrained JSONB column at the DB level."""
    from yt_live_dungeon.domain.errors import InvalidEnemyAttributesError

    if not isinstance(attributes, dict):
        raise InvalidEnemyAttributesError("attributes must be a mapping")

    actual_keys = set(attributes)
    expected_keys = set(ATTRIBUTE_MODIFIER_KEYS)
    if actual_keys != expected_keys:
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        raise InvalidEnemyAttributesError(
            f"attributes must have exactly the 10 attribute keys "
            f"(missing={sorted(missing)}, extra={sorted(extra)})"
        )

    for key, value in attributes.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidEnemyAttributesError(f"attribute value must be an int: {key!r}={value!r}")
