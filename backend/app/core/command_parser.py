from dataclasses import dataclass
from typing import Literal


@dataclass
class ParsedCommand:
    type: Literal["join", "yes", "no", "status", "spell", "unknown"]
    spell_name: str | None = None
    target_name: str | None = None


def parse(text: str) -> ParsedCommand:
    text = text.strip()
    if not text.startswith("@"):
        return ParsedCommand(type="unknown")

    parts = text.split(" ", 1)
    command_part = parts[0][1:]  # strip leading @
    target_part = parts[1].strip() or None if len(parts) > 1 else None

    # 半角英数字のみ許容。大文字・全角は不一致扱い。
    if not command_part or not command_part.isascii() or not command_part.isalnum():
        return ParsedCommand(type="unknown")

    match command_part:
        case "join":
            return ParsedCommand(type="join", target_name=target_part)
        case "yes":
            return ParsedCommand(type="yes")
        case "no":
            return ParsedCommand(type="no")
        case "status":
            return ParsedCommand(type="status")
        case _:
            return ParsedCommand(
                type="spell", spell_name=command_part, target_name=target_part
            )
