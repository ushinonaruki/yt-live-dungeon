import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.run import Run, RunState
from app.models.run_adventurer import RunAdventurer
from app.schemas.command import CommandEventIn
from app.services.battle_service import HinokinofutaResult, NoAliveEnemyError
from app.services.command_service import CommandService


def _make_run(state: RunState = RunState.BATTLE) -> Run:
    run = Run()
    run.id = uuid.uuid4()
    run.state = state
    run.current_floor = 1
    return run


def _make_adventurer() -> RunAdventurer:
    adv = RunAdventurer()
    adv.id = uuid.uuid4()
    adv.run_id = uuid.uuid4()
    adv.youtube_id = "yt_test"
    adv.nickname = "テスト冒険者"
    adv.hp = 255
    adv.max_hp = 255
    adv.str_val = 12
    adv.dex_val = 12
    adv.con_val = 12
    adv.int_val = 12
    adv.wis_val = 12
    adv.cha_val = 12
    adv.attr_red = 0
    adv.attr_blue = 0
    adv.attr_yellow = 0
    adv.attr_green = 0
    adv.attr_purple = 0
    adv.attr_orange = 0
    adv.faith = 0
    adv.joined_floor = 1
    adv.joined_at = datetime.now(timezone.utc)
    return adv


def _make_event(text: str = "@hinokinofuta") -> CommandEventIn:
    return CommandEventIn(
        youtube_id="yt_test",
        display_name="テストユーザー",
        text=text,
    )


def _make_service() -> CommandService:
    db = AsyncMock()
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)  # not on cooldown by default
    redis.set = AsyncMock()
    service = CommandService(db, redis)
    service.command_repo = MagicMock()
    service.command_repo.save = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
    service.log_repo = MagicMock()
    service.log_repo.add = AsyncMock()
    service.pending_join_repo = MagicMock()
    service.adventurer_repo = MagicMock()
    service.battle_service = MagicMock()
    return service


def _hinokinofuta_result(hp_before: int = 40, damage: int = 7) -> HinokinofutaResult:
    return HinokinofutaResult(
        target_enemy_id=uuid.uuid4(),
        target_display_name="スライム",
        damage=damage,
        hp_before=hp_before,
        hp_after=max(0, hp_before - damage),
        enemy_defeated=(hp_before - damage) <= 0,
    )


@pytest.mark.anyio
async def test_hinokinofuta_success():
    """battle 状態で生存冒険者がアイテムを所持 => 成功。"""
    service = _make_service()
    adv = _make_adventurer()

    service.adventurer_repo.get_alive_by_youtube_id = AsyncMock(return_value=adv)
    service.adventurer_repo.has_item_unlocking_spell = AsyncMock(return_value=True)
    service.battle_service.use_hinokinofuta = AsyncMock(
        return_value=_hinokinofuta_result()
    )

    result = await service.process(_make_run(RunState.BATTLE), _make_event())

    assert result.processed is True
    assert result.type == "spell"
    assert result.reason is None
    service.battle_service.use_hinokinofuta.assert_called_once()


@pytest.mark.anyio
async def test_hinokinofuta_not_in_battle():
    """waiting など battle 以外の状態では不発。"""
    service = _make_service()

    for state in (
        RunState.WAITING,
        RunState.RESULT,
        RunState.FLOOR_TRANSITION,
        RunState.GAME_OVER,
    ):
        result = await service.process(_make_run(state), _make_event())
        assert result.processed is False, f"state={state} should be unprocessed"
        assert result.reason == "not_in_battle"

    service.battle_service.use_hinokinofuta.assert_not_called()


@pytest.mark.anyio
async def test_hinokinofuta_not_joined():
    """未参加者（または戦死済み）は不発。"""
    service = _make_service()
    service.adventurer_repo.get_alive_by_youtube_id = AsyncMock(return_value=None)

    result = await service.process(_make_run(RunState.BATTLE), _make_event())

    assert result.processed is False
    assert result.reason == "not_joined"
    service.battle_service.use_hinokinofuta.assert_not_called()


@pytest.mark.anyio
async def test_hinokinofuta_spell_not_unlocked():
    """ひのきのフタを所持していない冒険者は不発。"""
    service = _make_service()
    adv = _make_adventurer()
    service.adventurer_repo.get_alive_by_youtube_id = AsyncMock(return_value=adv)
    service.adventurer_repo.has_item_unlocking_spell = AsyncMock(return_value=False)

    result = await service.process(_make_run(RunState.BATTLE), _make_event())

    assert result.processed is False
    assert result.reason == "spell_not_unlocked"
    service.battle_service.use_hinokinofuta.assert_not_called()


@pytest.mark.anyio
async def test_hinokinofuta_no_alive_enemy():
    """生存敵がいない場合、例外で API が落ちずに不発扱いになる。"""
    service = _make_service()
    adv = _make_adventurer()
    service.adventurer_repo.get_alive_by_youtube_id = AsyncMock(return_value=adv)
    service.adventurer_repo.has_item_unlocking_spell = AsyncMock(return_value=True)
    service.battle_service.use_hinokinofuta = AsyncMock(side_effect=NoAliveEnemyError())

    result = await service.process(_make_run(RunState.BATTLE), _make_event())

    assert result.processed is False
    assert result.reason == "no_alive_enemy"


@pytest.mark.anyio
async def test_command_always_saved_regardless_of_result():
    """不発でも commands テーブルへの保存は行われる。"""
    service = _make_service()

    # waiting 状態（不発ケース）
    await service.process(_make_run(RunState.WAITING), _make_event())

    service.command_repo.save.assert_called_once()


@pytest.mark.anyio
async def test_hinokinofuta_logs_are_delegated_to_battle_service():
    """spell_damage / enemy_defeated ログは BattleService 側の責務。
    command_service は use_hinokinofuta を呼ぶだけでよく、追加ログは出さない。"""
    service = _make_service()
    adv = _make_adventurer()
    service.adventurer_repo.get_alive_by_youtube_id = AsyncMock(return_value=adv)
    service.adventurer_repo.has_item_unlocking_spell = AsyncMock(return_value=True)
    service.battle_service.use_hinokinofuta = AsyncMock(
        return_value=_hinokinofuta_result()
    )

    await service.process(_make_run(RunState.BATTLE), _make_event())

    # command_service 側では log_repo.add を呼ばない（ログは battle_service に委譲）
    service.log_repo.add.assert_not_called()


@pytest.mark.anyio
async def test_hinokinofuta_on_cooldown():
    """クールタイム中は on_cooldown で不発。BattleService は呼ばれない。"""
    service = _make_service()
    adv = _make_adventurer()
    service.adventurer_repo.get_alive_by_youtube_id = AsyncMock(return_value=adv)
    service.adventurer_repo.has_item_unlocking_spell = AsyncMock(return_value=True)
    service.redis.exists = AsyncMock(return_value=1)  # on cooldown

    result = await service.process(_make_run(RunState.BATTLE), _make_event())

    assert result.processed is False
    assert result.reason == "on_cooldown"
    service.battle_service.use_hinokinofuta.assert_not_called()
    service.redis.set.assert_not_called()


@pytest.mark.anyio
async def test_hinokinofuta_sets_cooldown_on_success():
    """正常発動後に Redis に TTL=20秒でクールタイムが設定される。"""
    service = _make_service()
    adv = _make_adventurer()
    service.adventurer_repo.get_alive_by_youtube_id = AsyncMock(return_value=adv)
    service.adventurer_repo.has_item_unlocking_spell = AsyncMock(return_value=True)
    service.battle_service.use_hinokinofuta = AsyncMock(
        return_value=_hinokinofuta_result()
    )

    result = await service.process(_make_run(RunState.BATTLE), _make_event())

    assert result.processed is True
    service.redis.set.assert_called_once()
    call_args = service.redis.set.call_args
    assert call_args.args[0] == f"cooldown:adventurer:{adv.id}"
    assert call_args.kwargs.get("ex") == 20


@pytest.mark.anyio
async def test_hinokinofuta_no_cooldown_on_no_alive_enemy():
    """no_alive_enemy の場合、クールタイムを設定しない。"""
    service = _make_service()
    adv = _make_adventurer()
    service.adventurer_repo.get_alive_by_youtube_id = AsyncMock(return_value=adv)
    service.adventurer_repo.has_item_unlocking_spell = AsyncMock(return_value=True)
    service.battle_service.use_hinokinofuta = AsyncMock(side_effect=NoAliveEnemyError())

    result = await service.process(_make_run(RunState.BATTLE), _make_event())

    assert result.processed is False
    assert result.reason == "no_alive_enemy"
    service.redis.set.assert_not_called()


@pytest.mark.anyio
async def test_hinokinofuta_no_cooldown_on_not_joined():
    """not_joined の場合、クールタイムを設定しない。"""
    service = _make_service()
    service.adventurer_repo.get_alive_by_youtube_id = AsyncMock(return_value=None)

    result = await service.process(_make_run(RunState.BATTLE), _make_event())

    assert result.reason == "not_joined"
    service.redis.set.assert_not_called()


@pytest.mark.anyio
async def test_hinokinofuta_invalid_target_rejected():
    """target_rule=none のため対象指定がある入力は不発扱いになる。"""
    service = _make_service()

    for text in (
        "@hinokinofuta スライム",
        "@hinokinofuta anything",
        "@hinokinofuta 123",
    ):
        result = await service.process(
            _make_run(RunState.BATTLE), _make_event(text=text)
        )
        assert result.processed is False, f"'{text}' should be unprocessed"
        assert result.reason == "invalid_target"

    service.battle_service.use_hinokinofuta.assert_not_called()
