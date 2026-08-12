import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.api.deps import get_session
from yt_live_dungeon.api.schemas.command import CommandRequest, CommandResponse
from yt_live_dungeon.features.commands.submit import submit_command
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.persistence.queries.run import get_run

router = APIRouter()


@router.post(
    "/api/v1/runs/{run_id}/commands",
    response_model=CommandResponse,
    responses={404: {"description": "Run not found"}},
)
async def submit_run_command(
    run_id: uuid.UUID,
    payload: CommandRequest,
    session: AsyncSession = Depends(get_session),
) -> CommandResponse:
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    command_input = CommandInput(
        source=payload.source,
        source_message_id=payload.source_message_id,
        viewer_id=payload.viewer_id,
        viewer_display_name=payload.viewer_display_name,
        raw_text=payload.raw_text,
        received_at=payload.received_at,
    )
    record = await submit_command(session, run_id, command_input)

    return CommandResponse(processed=record.processed, reason=record.reason, result=record.result)
