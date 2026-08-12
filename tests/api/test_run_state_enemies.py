import uuid
from datetime import UTC, datetime, timedelta

import pytest

from yt_live_dungeon.api.deps import get_current_time
from yt_live_dungeon.app import app
from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Enemy,
    EnemyGroup,
    EnemyGroupMember,
    Run,
    RunEnemy,
    RunState,
)

FIXED_NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def frozen_now():
    """Overrides the get_current_time FastAPI dependency for the life of
    the test, via app.dependency_overrides -- the standard FastAPI
    injection-replacement mechanism, not a monkeypatch of any production
    module or route."""
    app.dependency_overrides[get_current_time] = lambda: FIXED_NOW
    yield FIXED_NOW
    del app.dependency_overrides[get_current_time]


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


async def _create_battle_scenario():
    async with async_session_factory() as session:
        master_enemy = Enemy(
            enemy_key=_unique("enemy"), display_name="Master Slime", base_max_hp=100,
            base_max_mp=20, base_attributes={}, break_max=50,
        )
        minion_enemy = Enemy(
            enemy_key=_unique("enemy"), display_name="Minion Slime", base_max_hp=50,
            base_max_mp=10, base_attributes={}, break_max=50,
        )
        session.add_all([master_enemy, minion_enemy])
        await session.flush()

        group = EnemyGroup(group_key=_unique("group"), display_name="Slime Duo")
        session.add(group)
        await session.flush()
        session.add_all(
            [
                EnemyGroupMember(
                    group_id=group.id, order_in_group=1, enemy_id=master_enemy.id, role="master"
                ),
                EnemyGroupMember(
                    group_id=group.id, order_in_group=2, enemy_id=minion_enemy.id, role="minion"
                ),
            ]
        )
        await session.flush()

        run = Run(state=RunState.BATTLE, current_floor=1, next_group_id=group.id)
        session.add(run)
        await session.flush()

        master_run_enemy = RunEnemy(
            run_id=run.id, floor=1, group_id=group.id, enemy_id=master_enemy.id,
            order_in_group=1, role="master", max_hp=100, hp=80, max_mp=20, mp=15,
            mp_regen_rate=1, mp_regen_updated_at=FIXED_NOW,
            attributes={"rr": 5}, defeated_at=None,
        )
        minion_run_enemy = RunEnemy(
            run_id=run.id, floor=1, group_id=group.id, enemy_id=minion_enemy.id,
            order_in_group=2, role="minion", max_hp=50, hp=0, max_mp=10, mp=10,
            mp_regen_rate=1, mp_regen_updated_at=FIXED_NOW,
            attributes={"rr": 3}, defeated_at=FIXED_NOW,
        )
        # a previous floor's enemy that must never appear in this
        # scenario's /state response
        stale_run_enemy = RunEnemy(
            run_id=run.id, floor=0, group_id=group.id, enemy_id=master_enemy.id,
            order_in_group=1, role="master", max_hp=100, hp=0, max_mp=20, mp=0,
            mp_regen_rate=1, mp_regen_updated_at=FIXED_NOW,
            attributes={}, defeated_at=FIXED_NOW,
        )
        session.add_all([master_run_enemy, minion_run_enemy, stale_run_enemy])
        await session.commit()

        return run.id, master_run_enemy, minion_run_enemy


async def test_state_returns_current_floor_enemies_with_required_fields(client, frozen_now):
    run_id, master_run_enemy, minion_run_enemy = await _create_battle_scenario()

    response = await client.get(f"/api/v1/runs/{run_id}/state")

    assert response.status_code == 200
    body = response.json()
    enemies_by_id = {e["id"]: e for e in body["enemies"]}
    assert set(enemies_by_id) == {str(master_run_enemy.id), str(minion_run_enemy.id)}

    master_dto = enemies_by_id[str(master_run_enemy.id)]
    assert master_dto["role"] == "master"
    assert master_dto["order_in_group"] == 1
    assert master_dto["max_hp"] == 100
    assert master_dto["hp"] == 80
    assert master_dto["max_mp"] == 20
    assert master_dto["mp"] == 15  # zero elapsed since mp_regen_updated_at == frozen_now
    assert master_dto["attributes"] == {"rr": 5}
    assert master_dto["is_alive"] is True
    assert master_dto["display_name"] == "Master Slime"
    assert isinstance(master_dto["enemy_key"], str)

    minion_dto = enemies_by_id[str(minion_run_enemy.id)]
    assert minion_dto["is_alive"] is False


async def test_state_excludes_a_previous_floors_enemies(client, frozen_now):
    run_id, master_run_enemy, minion_run_enemy = await _create_battle_scenario()

    response = await client.get(f"/api/v1/runs/{run_id}/state")

    body = response.json()
    assert len(body["enemies"]) == 2  # not 3 -- floor 0's stale row is excluded


async def test_state_does_not_expose_next_group_publicly(client, frozen_now):
    run_id, _master, _minion = await _create_battle_scenario()

    response = await client.get(f"/api/v1/runs/{run_id}/state")

    body = response.json()
    assert "next_group" not in body
    assert "next_group_id" not in body


async def _create_idle_regen_scenario(
    *, elapsed_seconds: int, regen_rate: int = 4, max_mp: int = 50
):
    """A single living enemy with mp=0 and a regen anchor `elapsed_seconds`
    before FIXED_NOW, so its logical mp at FIXED_NOW is deterministically
    `min(max_mp, elapsed_seconds * regen_rate)`."""
    async with async_session_factory() as session:
        enemy = Enemy(
            enemy_key=_unique("enemy"), display_name="Idle Slime", base_max_hp=100,
            base_max_mp=max_mp, base_attributes={}, break_max=50,
        )
        session.add(enemy)
        await session.flush()

        group = EnemyGroup(group_key=_unique("group"), display_name="Idle Group")
        session.add(group)
        await session.flush()
        session.add(
            EnemyGroupMember(group_id=group.id, order_in_group=1, enemy_id=enemy.id, role="master")
        )
        await session.flush()

        run = Run(state=RunState.BATTLE, current_floor=1)
        session.add(run)
        await session.flush()

        run_enemy = RunEnemy(
            run_id=run.id, floor=1, group_id=group.id, enemy_id=enemy.id,
            order_in_group=1, role="master", max_hp=100, hp=100, max_mp=max_mp, mp=0,
            mp_regen_rate=regen_rate,
            mp_regen_updated_at=FIXED_NOW - timedelta(seconds=elapsed_seconds),
            attributes={}, defeated_at=None,
        )
        session.add(run_enemy)
        await session.commit()

        return run.id, run_enemy


@pytest.mark.parametrize(
    ("elapsed_seconds", "expected_mp"),
    [
        (0, 0),
        (1, 4),
        (10, 40),
    ],
)
async def test_state_returns_the_exact_projected_mp_for_the_injected_now(
    client, frozen_now, elapsed_seconds, expected_mp
):
    run_id, run_enemy = await _create_idle_regen_scenario(elapsed_seconds=elapsed_seconds)

    response = await client.get(f"/api/v1/runs/{run_id}/state")

    body = response.json()
    dto = next(e for e in body["enemies"] if e["id"] == str(run_enemy.id))
    assert dto["mp"] == expected_mp


async def test_state_clamps_the_projected_mp_at_max_mp(client, frozen_now):
    # 20s * rate=4 = 80, well above max_mp=50 -- must clamp exactly
    run_id, run_enemy = await _create_idle_regen_scenario(elapsed_seconds=20, max_mp=50)

    response = await client.get(f"/api/v1/runs/{run_id}/state")

    body = response.json()
    dto = next(e for e in body["enemies"] if e["id"] == str(run_enemy.id))
    assert dto["mp"] == 50


async def test_state_returns_the_same_mp_across_repeated_requests_at_the_same_now(
    client, frozen_now
):
    run_id, run_enemy = await _create_idle_regen_scenario(elapsed_seconds=10)

    first = await client.get(f"/api/v1/runs/{run_id}/state")
    second = await client.get(f"/api/v1/runs/{run_id}/state")

    first_dto = next(e for e in first.json()["enemies"] if e["id"] == str(run_enemy.id))
    second_dto = next(e for e in second.json()["enemies"] if e["id"] == str(run_enemy.id))
    assert first_dto["mp"] == second_dto["mp"] == 40


async def test_state_does_not_persist_the_projected_mp(client, frozen_now):
    run_id, run_enemy = await _create_idle_regen_scenario(elapsed_seconds=10)

    await client.get(f"/api/v1/runs/{run_id}/state")

    async with async_session_factory() as session:
        refreshed = await session.get(RunEnemy, run_enemy.id)
        assert refreshed.mp == 0  # the read-only projection never wrote back
        assert refreshed.mp_regen_updated_at == FIXED_NOW - timedelta(seconds=10)
