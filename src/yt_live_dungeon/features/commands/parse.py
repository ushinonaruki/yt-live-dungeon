from dataclasses import dataclass

INVALID_SYNTAX = "invalid_syntax"

_SELECT_VALUES = {"1", "2", "3", "4"}


@dataclass(frozen=True)
class Login:
    pass


@dataclass(frozen=True)
class Logout:
    pass


@dataclass(frozen=True)
class Select:
    value: int


@dataclass(frozen=True)
class Ready:
    pass


@dataclass(frozen=True)
class Status:
    pass


@dataclass(frozen=True)
class Bag:
    pass


@dataclass(frozen=True)
class Move:
    order: str


@dataclass(frozen=True)
class Spell:
    command: str
    raw_argument: str


@dataclass(frozen=True)
class Unknown:
    reason: str


ParsedCommand = Login | Logout | Select | Ready | Status | Bag | Move | Spell | Unknown


def parse(raw_text: str) -> ParsedCommand:
    text = raw_text.strip()
    if not text.startswith("@"):
        return Unknown(reason=INVALID_SYNTAX)

    tokens = text[1:].split(maxsplit=1)
    if not tokens or not tokens[0]:
        return Unknown(reason=INVALID_SYNTAX)

    keyword = tokens[0]
    argument = tokens[1] if len(tokens) > 1 else ""

    if keyword == "login":
        return Login() if not argument else Unknown(reason=INVALID_SYNTAX)
    if keyword == "logout":
        return Logout() if not argument else Unknown(reason=INVALID_SYNTAX)
    if keyword == "ready":
        return Ready() if not argument else Unknown(reason=INVALID_SYNTAX)
    if keyword == "status":
        return Status() if not argument else Unknown(reason=INVALID_SYNTAX)
    if keyword == "bag":
        return Bag() if not argument else Unknown(reason=INVALID_SYNTAX)
    if keyword == "select":
        if argument in _SELECT_VALUES:
            return Select(value=int(argument))
        return Unknown(reason=INVALID_SYNTAX)
    if keyword == "move":
        if argument.isascii() and argument.isdigit():
            return Move(order=argument)
        return Unknown(reason=INVALID_SYNTAX)

    # Any other @keyword is a candidate spell command. Whether it names a
    # real, unlocked spell is a state/DB concern resolved later, not here.
    return Spell(command=keyword, raw_argument=argument)
