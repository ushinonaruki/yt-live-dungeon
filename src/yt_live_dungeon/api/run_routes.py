from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.api.deps import get_session
from yt_live_dungeon.api.schemas.run import RunCreateResponse
from yt_live_dungeon.features.run.create import create_run

router = APIRouter()


@router.post(
    "/api/v1/runs",
    response_model=RunCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_run_route(
    session: AsyncSession = Depends(get_session),
) -> RunCreateResponse:
    run = await create_run(session)
    await session.commit()
    await session.refresh(run)

    return RunCreateResponse(
        id=run.id,
        state=run.state,
        current_floor=run.current_floor,
        started_at=run.started_at,
        waiting_deadline_at=run.waiting_deadline_at,
    )
