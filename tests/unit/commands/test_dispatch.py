from yt_live_dungeon.features.commands.dispatch import CommandOutcome, dispatch
from yt_live_dungeon.features.commands.parse import Ready, Select


async def test_unregistered_command_returns_not_implemented():
    outcome = await dispatch(Ready(), handlers={}, context=None)

    assert outcome == CommandOutcome(processed=False, reason="not_implemented", result=None)


async def test_registered_handler_is_used_instead_of_fallback():
    calls = []

    async def fake_handler(command, context):
        calls.append((command, context))
        return CommandOutcome(processed=True, reason=None, result={"value": command.value})

    outcome = await dispatch(Select(value=2), handlers={Select: fake_handler}, context="ctx")

    assert outcome == CommandOutcome(processed=True, reason=None, result={"value": 2})
    assert calls == [(Select(value=2), "ctx")]


async def test_handlers_are_looked_up_per_call_not_from_shared_state():
    async def handler_a(command, context):
        return CommandOutcome(processed=True, reason=None, result={"handler": "a"})

    async def handler_b(command, context):
        return CommandOutcome(processed=True, reason=None, result={"handler": "b"})

    outcome_a = await dispatch(Ready(), handlers={Ready: handler_a}, context=None)
    outcome_b = await dispatch(Ready(), handlers={Ready: handler_b}, context=None)
    outcome_none = await dispatch(Ready(), handlers={}, context=None)

    assert outcome_a.result == {"handler": "a"}
    assert outcome_b.result == {"handler": "b"}
    assert outcome_none == CommandOutcome(processed=False, reason="not_implemented", result=None)
