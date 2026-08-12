from sqlalchemy import text


async def test_run_state_enum_values_are_lowercase(db_session):
    result = await db_session.execute(
        text("SELECT unnest(enum_range(NULL::runtime.run_state))::text AS value")
    )
    values = {row[0] for row in result}
    assert values == {"waiting", "battle", "camp", "retire", "game_over"}
