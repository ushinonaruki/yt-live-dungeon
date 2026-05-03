import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.run import RunState
from app.repositories.adventurer_repository import AdventurerRepository
from app.repositories.enemy_repository import EnemyRepository
from app.repositories.log_repository import LogRepository
from app.repositories.pending_join_repository import PendingJoinRepository
from app.repositories.run_repository import RunRepository
from app.schemas.log import LogOut
from app.schemas.run import (
    AdventurerOut,
    EnemyOut,
    FloorStartResult,
    PendingJoinOut,
    RunOut,
    RunStateOut,
)
from app.services.floor_service import FloorService, NoEnemiesError

router = APIRouter(prefix="/runs", tags=["runs"])

_FLOOR_START_ALLOWED = {RunState.WAITING, RunState.FLOOR_TRANSITION}


@router.post("", response_model=RunOut, status_code=201)
async def create_run(db: AsyncSession = Depends(get_db)):
    return await RunRepository(db).create()


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    run = await RunRepository(db).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/start-floor", response_model=FloorStartResult)
async def start_floor(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    run = await RunRepository(db).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.state not in _FLOOR_START_ALLOWED:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start floor in state '{run.state.value}'",
        )
    try:
        result = await FloorService(db).start_floor(run)
    except NoEnemiesError:
        raise HTTPException(
            status_code=409,
            detail="No enemies in database. Run: uv run alembic -c ../database/alembic.ini upgrade head",
        )
    return FloorStartResult(**result)


@router.get("/{run_id}/state", response_model=RunStateOut)
async def get_run_state(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    run = await RunRepository(db).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    pending_joins = await PendingJoinRepository(db).list_by_run(run_id)
    adventurers = await AdventurerRepository(db).list_by_run(run_id)
    enemy_rows = await EnemyRepository(db).list_by_run(run_id)

    return RunStateOut(
        run_id=run.id,
        state=run.state,
        current_floor=run.current_floor,
        total_deaths=run.total_deaths,
        pending_join_count=len(pending_joins),
        pending_joins=[PendingJoinOut.model_validate(j) for j in pending_joins],
        adventurers=[AdventurerOut.model_validate(a) for a in adventurers],
        enemies=[
            EnemyOut(
                id=e.id,
                enemy_id=e.enemy_id,
                display_name=display_name,
                floor=e.floor,
                hp=e.hp,
                max_hp=e.max_hp,
                position=e.position,
                role=e.role,
                is_alive=e.is_alive,
            )
            for e, display_name in enemy_rows
        ],
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
