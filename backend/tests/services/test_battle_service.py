import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.run import Run, RunState
from app.models.run_adventurer import RunAdventurer
from app.models.run_enemy import RunEnemy
from app.services.battle_service import (
    BattleService,
    HinokinofutaResult,
    NoAliveEnemyError,
)


def _make_run(run_id: uuid.UUID | None = None, floor: int = 1) -> Run:
    run = Run()
    run.id = run_id or uuid.uuid4()
    run.state = RunState.BATTLE
    run.current_floor = floor
    return run


def _make_run_enemy(
    hp: int, display_name: str = "スライム", role: str = "minion"
) -> tuple[RunEnemy, str]:
    enemy = RunEnemy()
    enemy.id = uuid.uuid4()
    enemy.run_id = uuid.uuid4()
    enemy.enemy_id = 1
    enemy.floor = 1
    enemy.hp = hp
    enemy.max_hp = hp
    enemy.position = 1
    enemy.role = role
    enemy.is_alive = True
    return enemy, display_name


def _make_adventurer(
    str_val: int = 12,
    dex_val: int = 12,
    con_val: int = 12,
    int_val: int = 12,
    wis_val: int = 12,
    cha_val: int = 12,
) -> RunAdventurer:
    adv = RunAdventurer()
    adv.id = uuid.uuid4()
    adv.run_id = uuid.uuid4()
    adv.youtube_id = "test_yt_id"
    adv.nickname = "テスト冒険者"
    adv.hp = 255
    adv.max_hp = 255
    adv.str_val = str_val
    adv.dex_val = dex_val
    adv.con_val = con_val
    adv.int_val = int_val
    adv.wis_val = wis_val
    adv.cha_val = cha_val
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


def _make_service() -> BattleService:
    db = MagicMock()
    service = BattleService(db)
    service.enemy_repo = MagicMock()
    service.log_repo = MagicMock()
    service.log_repo.add = AsyncMock()
    service.run_repo = MagicMock()
    service.run_repo.update_state = AsyncMock()
    return service


@pytest.mark.anyio
async def test_use_hinokinofuta_damages_enemy_survives():
    """ダメージ後にHPが残る場合、敵は生存したままになる。"""
    service = _make_service()
    run = _make_run()
    adv = _make_adventurer()  # 合計72, coeff=10 => damage=7
    enemy, name = _make_run_enemy(hp=40)

    service.enemy_repo.list_alive_by_run = AsyncMock(return_value=[(enemy, name)])
    service.enemy_repo.update_hp = AsyncMock(return_value=enemy)
    service.enemy_repo.mark_defeated = AsyncMock(return_value=enemy)

    result = await service.use_hinokinofuta(run=run, adventurer=adv)

    assert result.damage == 7
    assert result.hp_before == 40
    assert result.hp_after == 33
    assert result.enemy_defeated is False
    service.enemy_repo.update_hp.assert_called_once_with(enemy, 33)
    service.enemy_repo.mark_defeated.assert_not_called()


@pytest.mark.anyio
async def test_use_hinokinofuta_defeats_enemy_when_hp_reaches_zero():
    """ダメージでHPが0以下になる場合、敵を撃破扱いにする。"""
    service = _make_service()
    run = _make_run()
    adv = _make_adventurer()  # damage=7
    enemy, name = _make_run_enemy(hp=5)  # 5 - 7 = -2 => hp_after=0, defeated

    service.enemy_repo.list_alive_by_run = AsyncMock(return_value=[(enemy, name)])
    service.enemy_repo.update_hp = AsyncMock(return_value=enemy)
    service.enemy_repo.mark_defeated = AsyncMock(return_value=enemy)

    result = await service.use_hinokinofuta(run=run, adventurer=adv)

    assert result.damage == 7
    assert result.hp_before == 5
    assert result.hp_after == 0
    assert result.enemy_defeated is True
    service.enemy_repo.mark_defeated.assert_called_once()
    service.enemy_repo.update_hp.assert_not_called()


@pytest.mark.anyio
async def test_use_hinokinofuta_raises_when_no_alive_enemies():
    """生存敵がいない場合は NoAliveEnemyError を送出し、例外で落ちない。"""
    service = _make_service()
    run = _make_run()
    adv = _make_adventurer()

    service.enemy_repo.list_alive_by_run = AsyncMock(return_value=[])

    with pytest.raises(NoAliveEnemyError):
        await service.use_hinokinofuta(run=run, adventurer=adv)

    service.log_repo.add.assert_called_once()
    logged_event = service.log_repo.add.call_args.kwargs["event_type"]
    assert logged_event == "spell_no_target"


@pytest.mark.anyio
async def test_use_hinokinofuta_selects_from_multiple_enemies():
    """生存敵が複数いる場合、選ばれた1体にのみダメージが入る。"""
    service = _make_service()
    run = _make_run()
    adv = _make_adventurer()  # damage=7
    enemy1, name1 = _make_run_enemy(hp=50, display_name="スライムA")
    enemy2, name2 = _make_run_enemy(hp=60, display_name="スライムB")

    service.enemy_repo.list_alive_by_run = AsyncMock(
        return_value=[(enemy1, name1), (enemy2, name2)]
    )
    service.enemy_repo.update_hp = AsyncMock(return_value=enemy1)
    service.enemy_repo.mark_defeated = AsyncMock(return_value=enemy1)

    with patch("random.choice", return_value=(enemy1, name1)):
        result = await service.use_hinokinofuta(run=run, adventurer=adv)

    assert result.target_enemy_id == enemy1.id
    assert result.target_display_name == name1
    assert result.hp_before == 50
    assert result.hp_after == 43  # 50 - 7


@pytest.mark.anyio
async def test_use_hinokinofuta_logs_spell_damage():
    """攻撃成功時に spell_damage ログが記録される。"""
    service = _make_service()
    run = _make_run()
    adv = _make_adventurer()  # damage=7
    enemy, name = _make_run_enemy(hp=40)

    service.enemy_repo.list_alive_by_run = AsyncMock(return_value=[(enemy, name)])
    service.enemy_repo.update_hp = AsyncMock(return_value=enemy)
    service.enemy_repo.mark_defeated = AsyncMock(return_value=enemy)

    await service.use_hinokinofuta(run=run, adventurer=adv)

    calls = service.log_repo.add.call_args_list
    event_types = [c.kwargs["event_type"] for c in calls]
    assert "spell_damage" in event_types

    damage_log = next(c for c in calls if c.kwargs["event_type"] == "spell_damage")
    body = damage_log.kwargs["body"]
    assert body["spell"] == "hinokinofuta"
    assert body["damage"] == 7
    assert body["enemy_hp_before"] == 40
    assert body["enemy_hp_after"] == 33
    assert body["enemy_defeated"] is False


@pytest.mark.anyio
async def test_use_hinokinofuta_logs_enemy_defeated_when_killed():
    """撃破時に spell_damage に加えて enemy_defeated ログも記録される。"""
    service = _make_service()
    run = _make_run()
    adv = _make_adventurer()  # damage=7
    enemy, name = _make_run_enemy(hp=3)  # 3 - 7 = defeated

    service.enemy_repo.list_alive_by_run = AsyncMock(return_value=[(enemy, name)])
    service.enemy_repo.update_hp = AsyncMock(return_value=enemy)
    service.enemy_repo.mark_defeated = AsyncMock(return_value=enemy)

    await service.use_hinokinofuta(run=run, adventurer=adv)

    calls = service.log_repo.add.call_args_list
    event_types = [c.kwargs["event_type"] for c in calls]
    assert "spell_damage" in event_types
    assert "enemy_defeated" in event_types


@pytest.mark.anyio
async def test_master_defeated_transitions_run_to_result():
    """マスターを撃破すると run.state が RESULT に更新される。"""
    service = _make_service()
    run = _make_run(floor=1)
    adv = _make_adventurer()  # damage=7
    enemy, name = _make_run_enemy(hp=5, display_name="ゴブリン", role="master")

    service.enemy_repo.list_alive_by_run = AsyncMock(return_value=[(enemy, name)])
    service.enemy_repo.mark_defeated = AsyncMock(return_value=enemy)
    service.enemy_repo.update_hp = AsyncMock(return_value=enemy)

    await service.use_hinokinofuta(run=run, adventurer=adv)

    service.run_repo.update_state.assert_called_once_with(run, RunState.RESULT)


@pytest.mark.anyio
async def test_master_defeated_emits_floor_cleared_log():
    """マスター撃破時に floor_cleared ログが出る。"""
    service = _make_service()
    run = _make_run(floor=2)
    adv = _make_adventurer()  # damage=7
    enemy, name = _make_run_enemy(hp=3, display_name="ゴブリン王", role="master")

    service.enemy_repo.list_alive_by_run = AsyncMock(return_value=[(enemy, name)])
    service.enemy_repo.mark_defeated = AsyncMock(return_value=enemy)
    service.enemy_repo.update_hp = AsyncMock(return_value=enemy)

    await service.use_hinokinofuta(run=run, adventurer=adv)

    calls = service.log_repo.add.call_args_list
    event_types = [c.kwargs["event_type"] for c in calls]
    assert "floor_cleared" in event_types

    log = next(c for c in calls if c.kwargs["event_type"] == "floor_cleared")
    body = log.kwargs["body"]
    assert body["floor"] == 2
    assert body["master_enemy_id"] == str(enemy.id)
    assert body["master_display_name"] == "ゴブリン王"
    assert body["next_state"] == "result"


@pytest.mark.anyio
async def test_minion_defeated_does_not_change_state():
    """ミニオンを撃破しても run.state は変わらない。"""
    service = _make_service()
    run = _make_run()
    adv = _make_adventurer()  # damage=7
    enemy, name = _make_run_enemy(hp=3, role="minion")

    service.enemy_repo.list_alive_by_run = AsyncMock(return_value=[(enemy, name)])
    service.enemy_repo.mark_defeated = AsyncMock(return_value=enemy)
    service.enemy_repo.update_hp = AsyncMock(return_value=enemy)

    await service.use_hinokinofuta(run=run, adventurer=adv)

    service.run_repo.update_state.assert_not_called()
    calls = service.log_repo.add.call_args_list
    event_types = [c.kwargs["event_type"] for c in calls]
    assert "floor_cleared" not in event_types


@pytest.mark.anyio
async def test_enemy_not_defeated_does_not_change_state():
    """HPが残った場合、run.state は変わらない。"""
    service = _make_service()
    run = _make_run()
    adv = _make_adventurer()  # damage=7
    enemy, name = _make_run_enemy(hp=40, role="master")  # 40 - 7 = 33, survives

    service.enemy_repo.list_alive_by_run = AsyncMock(return_value=[(enemy, name)])
    service.enemy_repo.update_hp = AsyncMock(return_value=enemy)
    service.enemy_repo.mark_defeated = AsyncMock(return_value=enemy)

    await service.use_hinokinofuta(run=run, adventurer=adv)

    service.run_repo.update_state.assert_not_called()
