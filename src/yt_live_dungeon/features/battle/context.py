from dataclasses import dataclass, field
from typing import Protocol

# --------------------------------------------------------------------------
# Framework/ORM-independent contract between the Battle Engine and an
# EnemyPolicy. Nothing here may import SQLAlchemy, FastAPI, Redis, or any
# persistence/query module -- a Policy implementation must not be able to
# reach the database, issue further queries, or mutate game state. All
# dataclasses are frozen (read-only) for the same reason.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CombatantSnapshot:
    """A read-only, point-in-time view of one combatant (adventurer or
    enemy) as the Battle Engine sees it when building a decision
    context. `combatant_id` is that combatant's stable id as a string
    (a RunAdventurer.id or RunEnemy.id), never an ORM object."""

    combatant_id: str
    kind: str  # "adventurer" | "enemy"
    display_name: str
    role: str | None  # "master" | "minion" for kind == "enemy", else None
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    attributes: dict[str, int]
    is_alive: bool


@dataclass(frozen=True)
class LegalActionCandidate:
    """One Spell the acting enemy could legally cast right now, together
    with every legal target combination for it. The Battle Engine has
    already filtered this down to combinations that satisfy MP cost,
    target_rule, and combatant liveness -- a Policy chooses among these
    verbatim; it never invents a target combination of its own."""

    action_id: int  # Spell.id
    command: str
    mp_cost: int
    target_rule: str
    target_combinations: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class EnemyDecisionContext:
    """Everything an EnemyPolicy needs to choose one action, and nothing
    it could use to reach outside that choice. `action_sequence` is an
    opaque, caller-supplied identifier for this single decision instance
    (for logging/diagnostics only) -- double-apply prevention itself
    comes from the Battle Engine's row locking and single-commit
    transaction boundary, not from any identifier carried in this
    Context.
    """

    run_id: str
    floor: int
    action_sequence: int
    actor: CombatantSnapshot
    allies: tuple[CombatantSnapshot, ...]
    enemies: tuple[CombatantSnapshot, ...]
    legal_actions: tuple[LegalActionCandidate, ...]
    policy_config: dict


@dataclass(frozen=True)
class EnemyIntent:
    """A Policy's decision, and nothing else: no state-mutation
    instructions. The Battle Engine re-validates every field against the
    Context's legal_actions before applying anything."""

    action_id: int
    target_ids: tuple[str, ...]
    metadata: dict = field(default_factory=dict)


class EnemyPolicy(Protocol):
    def decide(self, context: EnemyDecisionContext) -> EnemyIntent: ...
