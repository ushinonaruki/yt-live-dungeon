import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.log_repository import LogRepository
from app.repositories.pending_join_repository import PendingJoinRepository
from app.repositories.run_repository import RunRepository
from app.schemas.log import LogOut
from app.schemas.run import PendingJoinOut, RunOut, RunStateOut

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunOut, status_code=201)
async def create_run(db: AsyncSession = Depends(get_db)):
    return await RunRepository(db).create()


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    run = await RunRepository(db).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{run_id}/state", response_model=RunStateOut)
async def get_run_state(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    run = await RunRepository(db).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    pending_joins = await PendingJoinRepository(db).list_by_run(run_id)
    return RunStateOut(
        run_id=run.id,
        state=run.state,
        current_floor=run.current_floor,
        total_deaths=run.total_deaths,
        pending_join_count=len(pending_joins),
        pending_joins=[PendingJoinOut.model_validate(j) for j in pending_joins],
    )


@router.get("/{run_id}/logs", response_model=list[LogOut])
async def get_run_logs(
    run_id: uuid.UUID,
    since: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    run = await RunRepository(db).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    logs = await LogRepository(db).list_by_run(run_id, since=since)
    return [LogOut.model_validate(log) for log in logs]
