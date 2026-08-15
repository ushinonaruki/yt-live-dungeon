import uuid
from datetime import UTC, datetime, timedelta

from yt_live_dungeon.persistence.database import async_session_factory
from yt_live_dungeon.persistence.models import (
    Enemy,
    EnemyGroup,
    EnemyGroupMember,
    Item,
    Run,
    RunAdventurer,
    RunCamp,
    RunCampMember,
    RunState,
    Spell,
    Spirit,
    SpiritItemPoolEntry,
)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


async def _create_open_camp_scenario():
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

        spirit = Spirit(
            spirit_key=_unique("spirit"),
            display_name="Test Spirit",
            representative_attribute="RR",
            blessing_item_id=blessing_item.id,
        )
        session.add(spirit)
        await session.flush()

        pool_item_a = Item(
            item_key=_unique("item"), display_name="Pool A", attribute="RR",
            granted_spell_id=spell.id,
        )
        pool_item_b = Item(
            item_key=_unique("item"), display_name="Pool B", attribute="RR",
            granted_spell_id=spell.id,
        )
        candidate_a = Item(
            item_key=_unique("item"), display_name="Candidate A", attribute="RR",
            granted_spell_id=spell.id,
        )
        candidate_b = Item(
            item_key=_unique("item"), display_name="Candidate B", attribute="RR",
            granted_spell_id=spell.id,
        )
        session.add_all([pool_item_a, pool_item_b, candidate_a, candidate_b])
        await session.flush()
        # this spirit is committed for real, so it must satisfy the same
        # "at least 2 active pool items" invariant seed data does
        session.add(SpiritItemPoolEntry(spirit_id=spirit.id, item_id=pool_item_a.id))
        session.add(SpiritItemPoolEntry(spirit_id=spirit.id, item_id=pool_item_b.id))

        enemy = Enemy(
            enemy_key=_unique("enemy"),
            display_name="Test Enemy",
            base_max_hp=100,
            base_max_mp=100,
            base_attributes={},
            break_max=50,
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

        run = Run(state=RunState.CAMP, current_floor=1, next_group_id=enemy_group.id)
        session.add(run)
        await session.flush()

        adventurer = RunAdventurer(run_id=run.id, youtube_id=_unique("viewer"), hp=500, mp=100)
        session.add(adventurer)
        await session.flush()

        started_at = datetime.now(UTC)
        camp = RunCamp(
            run_id=run.id,
            floor=1,
            spirit_id=spirit.id,
            candidate_a_item_id=candidate_a.id,
            candidate_b_item_id=candidate_b.id,
            started_at=started_at,
            deadline_at=started_at + timedelta(minutes=5),
        )
        session.add(camp)
        await session.flush()

        session.add(
            RunCampMember(camp_id=camp.id, run_adventurer_id=adventurer.id, can_select_action=True)
        )
        await session.commit()

        return run.id, adventurer


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


async def test_login_via_command_endpoint_adds_a_camp_member(client):
    run_id, existing = await _create_open_camp_scenario()
    new_viewer = _unique("new-viewer")

    response = await _submit(client, run_id, new_viewer, "@login")

    assert response.status_code == 200
    assert response.json()["processed"] is True

    state = await client.get(f"/api/v1/runs/{run_id}/state")
    members = state.json()["camp"]["members"]
    assert len(members) == 2
    new_member = next(
        m for m in members if m["run_adventurer_id"] != str(existing.id)
    )
    assert new_member["can_select_action"] is False
    assert new_member["is_ready"] is False


async def test_logout_via_command_endpoint_removes_participant_from_state(client):
    run_id, adventurer = await _create_open_camp_scenario()
    new_viewer = _unique("new-viewer")
    await _submit(client, run_id, new_viewer, "@login")

    response = await _submit(client, run_id, adventurer.youtube_id, "@logout")

    assert response.status_code == 200
    assert response.json()["processed"] is True

    state = await client.get(f"/api/v1/runs/{run_id}/state")
    body = state.json()
    assert body["state"] == "camp"  # the other participant is still here, unready
    members_by_id = {m["run_adventurer_id"]: m for m in body["camp"]["members"]}
    # the CampMemberResponse contract keeps a logged-out member's row
    # (history), just flagged as no longer participating -- it is not
    # removed from the list entirely
    assert members_by_id[str(adventurer.id)]["is_participating"] is False


async def test_ready_via_command_endpoint_can_end_camp_and_advance_floor(client):
    run_id, adventurer = await _create_open_camp_scenario()

    response = await _submit(client, run_id, adventurer.youtube_id, "@ready")

    assert response.status_code == 200
    assert response.json()["processed"] is True

    state = await client.get(f"/api/v1/runs/{run_id}/state")
    body = state.json()
    assert body["state"] == "battle"
    assert body["current_floor"] == 2
    assert body["camp"] is None


async def test_login_rejected_reason_surfaces_through_command_endpoint(client):
    run_id, adventurer = await _create_open_camp_scenario()

    response = await _submit(client, run_id, adventurer.youtube_id, "@login")

    assert response.status_code == 200
    body = response.json()
    assert body["processed"] is False
    assert body["reason"] == "already_joined"


async def test_duplicate_source_message_id_does_not_double_login(client):
    run_id, _adventurer = await _create_open_camp_scenario()
    new_viewer = _unique("new-viewer")
    payload = {
        "source": "youtube_live",
        "source_message_id": _unique("dup-msg"),
        "viewer_id": new_viewer,
        "viewer_display_name": "viewer",
        "raw_text": "@login",
        "received_at": datetime.now(UTC).isoformat(),
    }

    first = await client.post(f"/api/v1/runs/{run_id}/commands", json=payload)
    second = await client.post(f"/api/v1/runs/{run_id}/commands", json=payload)

    assert first.json()["processed"] is True
    assert second.json() == first.json()

    state = await client.get(f"/api/v1/runs/{run_id}/state")
    members = state.json()["camp"]["members"]
    assert len(members) == 2  # the original participant plus exactly one new login
