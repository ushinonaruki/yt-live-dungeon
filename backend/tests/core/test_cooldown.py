import json
import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.cooldown import cooldown_key, is_on_cooldown, set_cooldown


def test_cooldown_key_format():
    adv_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert (
        cooldown_key(adv_id)
        == "cooldown:adventurer:12345678-1234-5678-1234-567812345678"
    )


@pytest.mark.anyio
async def test_is_on_cooldown_true_when_key_exists():
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=1)
    assert await is_on_cooldown(redis, uuid.uuid4()) is True


@pytest.mark.anyio
async def test_is_on_cooldown_false_when_key_absent():
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)
    assert await is_on_cooldown(redis, uuid.uuid4()) is False


@pytest.mark.anyio
async def test_set_cooldown_uses_correct_key_and_ttl():
    redis = AsyncMock()
    redis.set = AsyncMock()
    adv_id = uuid.uuid4()

    await set_cooldown(redis, adv_id, "hinokinofuta", 20)

    redis.set.assert_called_once()
    args = redis.set.call_args
    assert args.args[0] == f"cooldown:adventurer:{adv_id}"
    assert args.kwargs.get("ex") == 20


@pytest.mark.anyio
async def test_set_cooldown_value_contains_spell_name_and_expires_at():
    redis = AsyncMock()
    redis.set = AsyncMock()

    await set_cooldown(redis, uuid.uuid4(), "hinokinofuta", 20)

    raw = redis.set.call_args.args[1]
    data = json.loads(raw)
    assert data["spell_name"] == "hinokinofuta"
    assert "expires_at" in data
    assert data["expires_at"].endswith("Z")
