from yt_live_dungeon.app import app


def _schema():
    return app.openapi()


def test_command_endpoint_method_and_path_are_fixed():
    paths = _schema()["paths"]
    assert "post" in paths["/api/v1/runs/{run_id}/commands"]


def test_state_endpoint_method_and_path_are_fixed():
    paths = _schema()["paths"]
    assert "get" in paths["/api/v1/runs/{run_id}/state"]


def test_events_endpoint_method_and_path_are_fixed():
    paths = _schema()["paths"]
    assert "get" in paths["/api/v1/runs/{run_id}/events"]


def test_command_endpoint_request_and_response_schema_refs():
    operation = _schema()["paths"]["/api/v1/runs/{run_id}/commands"]["post"]

    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["$ref"] == "#/components/schemas/CommandRequest"

    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"] == "#/components/schemas/CommandResponse"

    assert "404" in operation["responses"]
    assert "422" in operation["responses"]


def test_command_request_schema_required_fields_and_types():
    schema = _schema()["components"]["schemas"]["CommandRequest"]

    assert schema["required"] == [
        "source",
        "source_message_id",
        "viewer_id",
        "viewer_display_name",
        "raw_text",
        "received_at",
    ]
    assert schema["properties"]["source"]["type"] == "string"
    assert schema["properties"]["source"]["minLength"] == 1
    assert schema["properties"]["source"]["maxLength"] == 32
    assert schema["properties"]["source_message_id"]["type"] == "string"
    assert schema["properties"]["source_message_id"]["minLength"] == 1
    assert schema["properties"]["source_message_id"]["maxLength"] == 256
    assert schema["properties"]["viewer_id"]["type"] == "string"
    assert schema["properties"]["viewer_id"]["minLength"] == 1
    assert schema["properties"]["viewer_id"]["maxLength"] == 256
    assert schema["properties"]["received_at"]["type"] == "string"
    assert schema["properties"]["received_at"]["format"] == "date-time"


def test_command_response_schema_required_fields_and_types():
    schema = _schema()["components"]["schemas"]["CommandResponse"]

    assert schema["required"] == ["processed", "reason", "result"]
    assert schema["properties"]["processed"]["type"] == "boolean"
    assert {"type": "string"} in schema["properties"]["reason"]["anyOf"]
    assert {"type": "null"} in schema["properties"]["reason"]["anyOf"]


def test_state_endpoint_response_schema_ref_and_error_responses():
    operation = _schema()["paths"]["/api/v1/runs/{run_id}/state"]["get"]

    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"] == "#/components/schemas/RunStateResponse"
    assert "404" in operation["responses"]


def test_run_state_response_schema_required_fields_and_types():
    schema = _schema()["components"]["schemas"]["RunStateResponse"]

    assert schema["required"] == [
        "id",
        "state",
        "current_floor",
        "started_at",
        "ended_at",
    ]
    assert schema["properties"]["id"]["type"] == "string"
    assert schema["properties"]["id"]["format"] == "uuid"
    assert schema["properties"]["state"]["$ref"] == "#/components/schemas/RunState"
    assert schema["properties"]["current_floor"]["type"] == "integer"
    assert schema["properties"]["started_at"]["format"] == "date-time"


def test_run_state_enum_values_are_fixed():
    schema = _schema()["components"]["schemas"]["RunState"]

    assert schema["type"] == "string"
    assert schema["enum"] == ["waiting", "battle", "camp", "retire", "game_over"]


def test_events_endpoint_query_parameter_and_response_schema():
    operation = _schema()["paths"]["/api/v1/runs/{run_id}/events"]["get"]

    after_param = next(p for p in operation["parameters"] if p["name"] == "after")
    assert after_param["in"] == "query"
    assert after_param["required"] is False
    assert after_param["schema"]["type"] == "integer"
    assert after_param["schema"]["default"] == 0

    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"] == "#/components/schemas/EventListResponse"
    assert "404" in operation["responses"]


def test_event_list_and_event_response_schema_required_fields_and_types():
    schemas = _schema()["components"]["schemas"]

    event_list_schema = schemas["EventListResponse"]
    assert event_list_schema["required"] == ["events"]
    assert event_list_schema["properties"]["events"]["type"] == "array"
    assert (
        event_list_schema["properties"]["events"]["items"]["$ref"]
        == "#/components/schemas/EventResponse"
    )

    event_schema = schemas["EventResponse"]
    assert event_schema["required"] == ["sequence", "event_type", "body", "created_at"]
    assert event_schema["properties"]["sequence"]["type"] == "integer"
    assert event_schema["properties"]["event_type"]["type"] == "string"
    assert event_schema["properties"]["body"]["type"] == "object"
    assert event_schema["properties"]["created_at"]["format"] == "date-time"


def test_run_state_response_camp_field_is_nullable_reference():
    schema = _schema()["components"]["schemas"]["RunStateResponse"]

    camp_field = schema["properties"]["camp"]
    refs = [entry.get("$ref") for entry in camp_field["anyOf"]]
    nulls = [entry.get("type") for entry in camp_field["anyOf"]]
    assert "#/components/schemas/CampStateResponse" in refs
    assert "null" in nulls
    # camp is not part of the required list: a non-CAMP run response omits
    # the field being mandatory, but the route always emits it explicitly
    # (null when not in camp).
    assert "camp" not in schema["required"]


def test_camp_state_response_schema_required_fields_and_types():
    schema = _schema()["components"]["schemas"]["CampStateResponse"]

    assert schema["required"] == [
        "floor",
        "started_at",
        "deadline_at",
        "candidate_a",
        "candidate_b",
        "members",
    ]
    assert schema["properties"]["floor"]["type"] == "integer"
    assert schema["properties"]["started_at"]["format"] == "date-time"
    assert schema["properties"]["deadline_at"]["format"] == "date-time"
    candidate_ref = "#/components/schemas/CampCandidateResponse"
    assert schema["properties"]["candidate_a"]["$ref"] == candidate_ref
    assert schema["properties"]["candidate_b"]["$ref"] == candidate_ref
    assert schema["properties"]["members"]["type"] == "array"
    assert (
        schema["properties"]["members"]["items"]["$ref"]
        == "#/components/schemas/CampMemberResponse"
    )


def test_camp_candidate_response_schema_required_fields_and_types():
    schema = _schema()["components"]["schemas"]["CampCandidateResponse"]

    assert schema["required"] == ["item_id", "display_name"]
    assert schema["properties"]["item_id"]["type"] == "integer"
    assert schema["properties"]["display_name"]["type"] == "string"


def test_camp_member_response_schema_required_fields_and_types():
    schema = _schema()["components"]["schemas"]["CampMemberResponse"]

    assert schema["required"] == [
        "run_adventurer_id",
        "can_select_action",
        "selected_action",
        "is_ready",
        "is_participating",
    ]
    assert schema["properties"]["run_adventurer_id"]["type"] == "string"
    assert schema["properties"]["run_adventurer_id"]["format"] == "uuid"
    assert schema["properties"]["can_select_action"]["type"] == "boolean"
    assert {"type": "string"} in schema["properties"]["selected_action"]["anyOf"]
    assert {"type": "null"} in schema["properties"]["selected_action"]["anyOf"]
    assert schema["properties"]["is_ready"]["type"] == "boolean"
    assert schema["properties"]["is_participating"]["type"] == "boolean"
