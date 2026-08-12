import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.api.deps import get_session
from yt_live_dungeon.api.schemas.event import EventListResponse, EventResponse
from yt_live_dungeon.api.schemas.run_state import RunStateResponse
from yt_live_dungeon.persistence.queries.event import list_events_after
from yt_live_dungeon.persistence.queries.run import get_run

router = APIRouter()


@router.get(
    "/api/v1/runs/{run_id}/state",
    response_model=RunStateResponse,
    responses={404: {"description": "Run not found"}},
)
async def get_run_state(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> RunStateResponse:
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    return RunStateResponse(
        id=run.id,
        state=run.state,
        current_floor=run.current_floor,
        started_at=run.started_at,
        ended_at=run.ended_at,
    )


@router.get(
    "/api/v1/runs/{run_id}/events",
    response_model=EventListResponse,
    responses={404: {"description": "Run not found"}},
)
async def get_run_events(
    run_id: uuid.UUID,
    after: int = 0,
    session: AsyncSession = Depends(get_session),
) -> EventListResponse:
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    events = await list_events_after(session, run_id, after)

    return EventListResponse(
        events=[
            EventResponse(
                sequence=event.sequence,
                event_type=event.event_type,
                body=event.body,
                created_at=event.created_at,
            )
            for event in events
        ]
    )
