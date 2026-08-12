from dataclasses import dataclass

MAX_SLOTS = 8


@dataclass(frozen=True)
class ItemDefinition:
    item_id: int
    attribute: str
    granted_spell_id: int
    base_stat_modifiers: dict
    per_level_stat_modifiers: dict


@dataclass(frozen=True)
class InventoryEntry:
    slot: int
    current_level: int
    definition: ItemDefinition
