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


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


async def _create_camp_scenario(*, started_at: datetime | None = None):
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

        candidate_a = Item(
            item_key=_unique("item"), display_name="Candidate A", attribute="RR",
            granted_spell_id=spell.id,
        )
        candidate_b = Item(
            item_key=_unique("item"), display_name="Candidate B", attribute="RR",
            granted_spell_id=spell.id,
        )
        session.add_all([candidate_a, candidate_b])
        await session.flush()
        session.add(SpiritItemPoolEntry(spirit_id=spirit.id, item_id=candidate_a.id))
        session.add(SpiritItemPoolEntry(spirit_id=spirit.id, item_id=candidate_b.id))

        enemy = Enemy(
            enemy_key=_unique("enemy"),
            display_name="Test Enemy",
            base_max_hp=100,
            base_max_mp=20,
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

        run = Run(state=RunState.CAMP, current_floor=2, next_group_id=enemy_group.id)
        session.add(run)
        await session.flush()

        adventurer_1 = RunAdventurer(run_id=run.id, youtube_id=_unique("viewer"), hp=500, mp=100)
        adventurer_2 = RunAdventurer(run_id=run.id, youtube_id=_unique("viewer"), hp=500, mp=100)
        session.add_all([adventurer_1, adventurer_2])
        await session.flush()

        # Deliberately anchored to real wall-clock time by default, not a
        # fixed past timestamp: state fetches now evaluate the CAMP
        # deadline against datetime.now(UTC), so a hardcoded past
        # started_at would make this scenario read as already-expired
        # unless a caller deliberately opts into that via the parameter.
        started_at = started_at or datetime.now(UTC)
        camp = RunCamp(
            run_id=run.id,
            floor=2,
            spirit_id=spirit.id,
            candidate_a_item_id=candidate_a.id,
            candidate_b_item_id=candidate_b.id,
            started_at=started_at,
            deadline_at=started_at + timedelta(minutes=5),
        )
        session.add(camp)
        await session.flush()

        session.add(
            RunCampMember(
                camp_id=camp.id, run_adventurer_id=adventurer_1.id, can_select_action=True
            )
        )
        session.add(
            RunCampMember(
                camp_id=camp.id,
                run_adventurer_id=adventurer_2.id,
                can_select_action=True,
                ready_at=started_at,
            )
        )
        await session.commit()

        return run.id, camp, candidate_a, candidate_b, adventurer_1, adventurer_2, spirit


async def test_state_includes_camp_block_when_in_camp(client):
    (
        run_id,
        camp,
        candidate_a,
        candidate_b,
        adventurer_1,
        adventurer_2,
        _spirit,
    ) = await _create_camp_scenario()

    response = await client.get(f"/api/v1/runs/{run_id}/state")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "camp"

    camp_body = body["camp"]
    assert camp_body["floor"] == 2
    assert _parse_iso(camp_body["deadline_at"]) == camp.deadline_at
    assert camp_body["candidate_a"] == {
        "item_id": candidate_a.id,
        "display_name": candidate_a.display_name,
    }
    assert camp_body["candidate_b"] == {
        "item_id": candidate_b.id,
        "display_name": candidate_b.display_name,
    }

    members_by_id = {m["run_adventurer_id"]: m for m in camp_body["members"]}
    assert members_by_id[str(adventurer_1.id)]["can_select_action"] is True
    assert members_by_id[str(adventurer_1.id)]["selected_action"] is None
    assert members_by_id[str(adventurer_1.id)]["is_ready"] is False
    assert members_by_id[str(adventurer_1.id)]["is_participating"] is True
    assert members_by_id[str(adventurer_2.id)]["is_ready"] is True
    assert len(camp_body["members"]) == 2


async def test_state_candidates_are_not_duplicated_per_member(client):
    run_id, camp, *_ = await _create_camp_scenario()

    response = await client.get(f"/api/v1/runs/{run_id}/state")

    body = response.json()
    # candidates are a single shared pair at the top level, not repeated
    # inside each member entry
    for member in body["camp"]["members"]:
        assert "candidate_a" not in member
        assert "candidate_b" not in member


async def test_events_after_returns_camp_action_event_triggered_via_command(client):
    run_id, camp, candidate_a, candidate_b, adventurer_1, _a2, _spirit = (
        await _create_camp_scenario()
    )

    baseline = await client.get(f"/api/v1/runs/{run_id}/events")
    after_sequence = max((e["sequence"] for e in baseline.json()["events"]), default=0)

    payload = {
        "source": "youtube_live",
        "source_message_id": _unique("msg"),
        "viewer_id": adventurer_1.youtube_id,
        "viewer_display_name": "viewer",
        "raw_text": "@select 1",
        "received_at": datetime.now(UTC).isoformat(),
    }
    command_response = await client.post(f"/api/v1/runs/{run_id}/commands", json=payload)
    assert command_response.status_code == 200
    assert command_response.json()["processed"] is True

    events_response = await client.get(
        f"/api/v1/runs/{run_id}/events", params={"after": after_sequence}
    )
    events = events_response.json()["events"]

    assert len(events) == 1
    assert events[0]["event_type"] == "camp_action_selected"
    assert events[0]["body"]["adventurer"] == str(adventurer_1.id)


async def test_state_fetch_alone_detects_and_enforces_a_passed_deadline(client):
    """There is no resident scheduler in this headless build -- a GET
    /state call is itself an entry point that must notice and enforce an
    expired CAMP, with no command required first."""
    long_past = datetime.now(UTC) - timedelta(hours=1)
    run_id, _camp, *_ = await _create_camp_scenario(started_at=long_past)

    response = await client.get(f"/api/v1/runs/{run_id}/state")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "battle"
    assert body["camp"] is None
