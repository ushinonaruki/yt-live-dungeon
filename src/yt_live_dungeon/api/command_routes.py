import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from yt_live_dungeon.api.deps import get_session
from yt_live_dungeon.api.schemas.command import CommandRequest, CommandResponse
from yt_live_dungeon.features.camp.handlers import build_camp_handlers
from yt_live_dungeon.features.commands.submit import submit_command
from yt_live_dungeon.features.commands.types import CommandInput
from yt_live_dungeon.features.waiting.handlers import build_waiting_handlers
from yt_live_dungeon.persistence.models import RunState
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
    # The handler registry is picked from this unlocked read of run.state
    # alone -- submit_command() itself locks the run row FOR UPDATE before
    # a handler runs, and every WAITING/CAMP handler re-checks the state
    # it actually needs under that lock, so a stale read here (the state
    # changing between this check and the locked handler run) can only
    # ever cause a correct rejection, never a wrong handler actually
    # mutating state for the wrong run phase.
    handlers = build_waiting_handlers() if run.state == RunState.WAITING else build_camp_handlers()
    record = await submit_command(session, run_id, command_input, handlers=handlers)

    return CommandResponse(processed=record.processed, reason=record.reason, result=record.result)
