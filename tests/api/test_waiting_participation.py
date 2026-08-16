import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Egregore,
    EgregoreItemPoolEntry,
    Enemy,
    EnemyGroup,
    EnemyGroupMember,
    Item,
    Run,
    RunAdventurer,
    RunState,
    Spell,
)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


async def _create_waiting_scenario():
    async with async_session_factory() as session:
        spell = Spell(
            command=_unique("spell"),
            display_name="Firebolt",
            attribute="RR",
            mp_cost=5,
            target_rule="single_enemy",
            effects=[{"type": "damage", "power": 5}],
        )
        session.add(spell)
        await session.flush()

        blessing_item = Item(
            item_key=_unique("item"), display_name="Blessing", attribute="RR",
            granted_spell_id=spell.id,
        )
        session.add(blessing_item)
        await session.flush()

        egregore = Egregore(
            egregore_key=_unique("egregore"),
            display_name="Test Egregore",
            representative_attribute="RR",
            blessing_item_id=blessing_item.id,
        )
        session.add(egregore)
        await session.flush()

        pool_item_a = Item(
            item_key=_unique("item"), display_name="Pool A", attribute="RR",
            granted_spell_id=spell.id,
        )
        pool_item_b = Item(
            item_key=_unique("item"), display_name="Pool B", attribute="RR",
            granted_spell_id=spell.id,
        )
        session.add_all([pool_item_a, pool_item_b])
        await session.flush()
        session.add(EgregoreItemPoolEntry(egregore_id=egregore.id, item_id=pool_item_a.id))
        session.add(EgregoreItemPoolEntry(egregore_id=egregore.id, item_id=pool_item_b.id))

        enemy = Enemy(
            enemy_key=_unique("enemy"), display_name="Test Enemy", base_max_hp=100,
            base_max_mp=100, base_attributes={}, break_max=50,
        )
        session.add(enemy)
        await session.flush()
        enemy_group = EnemyGroup(group_key=_unique("group"), display_name="Test Group")
        session.add(enemy_group)
        await session.flush()
        session.add(
            EnemyGroupMember(
                group_id=enemy_group.id, order_in_group=1, enemy_id=enemy.id, role="master"
            )
        )
        await session.flush()

        run = Run(state=RunState.WAITING)
        session.add(run)
        await session.commit()

        return run.id


async def _submit(client, run_id, viewer_id: str, raw_text: str):
    payload = {
        "source": "youtube_live",
        "source_message_id": _unique("msg"),
        "viewer_id": viewer_id,
        "viewer_display_name": "viewer",
        "raw_text": raw_text,
        "received_at": datetime.now(UTC).isoformat(),
    }
    return await client.post(f"/api/v1/runs/{run_id}/commands", json=payload)


async def test_login_via_command_endpoint_onboards_new_adventurer(client):
    run_id = await _create_waiting_scenario()
    viewer = _unique("viewer")

    response = await _submit(client, run_id, viewer, "@login")

    assert response.status_code == 200
    assert response.json()["processed"] is True

    state = await client.get(f"/api/v1/runs/{run_id}/state")
    assert state.json()["state"] == "waiting"


async def test_ready_via_command_endpoint_starts_floor_1_when_all_ready(client):
    run_id = await _create_waiting_scenario()
    viewer = _unique("viewer")
    await _submit(client, run_id, viewer, "@login")

    response = await _submit(client, run_id, viewer, "@ready")

    assert response.status_code == 200
    assert response.json()["processed"] is True

    state = await client.get(f"/api/v1/runs/{run_id}/state")
    body = state.json()
    assert body["state"] == "battle"
    assert body["current_floor"] == 1
    assert len(body["enemies"]) == 1


async def test_duplicate_source_message_id_does_not_double_login_during_waiting(client):
    run_id = await _create_waiting_scenario()
    viewer = _unique("viewer")
    payload = {
        "source": "youtube_live",
        "source_message_id": _unique("dup-msg"),
        "viewer_id": viewer,
        "viewer_display_name": "viewer",
        "raw_text": "@login",
        "received_at": datetime.now(UTC).isoformat(),
    }

    first = await client.post(f"/api/v1/runs/{run_id}/commands", json=payload)
    second = await client.post(f"/api/v1/runs/{run_id}/commands", json=payload)

    assert first.json()["processed"] is True
    assert second.json() == first.json()

    async with async_session_factory() as session:
        count = (
            await session.execute(
                select(func.count())
                .select_from(RunAdventurer)
                .where(RunAdventurer.run_id == run_id)
            )
        ).scalar_one()
    assert count == 1


async def test_login_against_non_waiting_run_is_routed_to_camp_handlers(client):
    async with async_session_factory() as session:
        run = Run(state=RunState.BATTLE, current_floor=1)
        session.add(run)
        await session.commit()
        run_id = run.id

    response = await _submit(client, run_id, _unique("viewer"), "@login")

    assert response.status_code == 200
    body = response.json()
    assert body["processed"] is False
    assert body["reason"] == "not_in_camp"
