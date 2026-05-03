import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.run_repository import RunRepository
from app.schemas.command import CommandEventIn
from app.services.command_service import CommandService

router = APIRouter(prefix="/runs", tags=["commands"])


@router.post("/{run_id}/commands")
async def post_command(
    run_id: uuid.UUID,
    event: CommandEventIn,
    db: AsyncSession = Depends(get_db),
):
    run = await RunRepository(db).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    return await CommandService(db).process(run, event)
