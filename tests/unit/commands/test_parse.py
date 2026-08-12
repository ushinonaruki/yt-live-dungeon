import pytest

from yt_live_dungeon.features.commands.parse import (
    Bag,
    Login,
    Logout,
    Move,
    Ready,
    Select,
    Spell,
    Status,
    Unknown,
    parse,
)


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("@login", Login()),
        ("@logout", Logout()),
        ("@ready", Ready()),
        ("@status", Status()),
        ("@bag", Bag()),
        ("@select 1", Select(value=1)),
        ("@select 2", Select(value=2)),
        ("@select 3", Select(value=3)),
        ("@select 4", Select(value=4)),
        ("@move 31425", Move(order="31425")),
        ("@firebolt foo", Spell(command="firebolt", raw_argument="foo")),
        ("@firebolt", Spell(command="firebolt", raw_argument="")),
    ],
)
def test_parses_recognized_command_syntax(raw_text, expected):
    assert parse(raw_text) == expected


@pytest.mark.parametrize(
    "raw_text",
    [
        "",
        "hello",
        "@",
        "@login extra",
        "@logout extra",
        "@ready extra",
        "@status extra",
        "@bag extra",
        "@select",
        "@select 5",
        "@select abc",
        "@move",
        "@move abc",
        "@move ３１４２５",  # fullwidth digits, not ASCII
    ],
)
def test_rejects_invalid_syntax(raw_text):
    result = parse(raw_text)
    assert isinstance(result, Unknown)
    assert result.reason == "invalid_syntax"
