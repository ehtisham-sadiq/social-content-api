from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app import crud, models, schemas
from app.database import get_db
from app.auth import get_current_active_user

router = APIRouter(
    prefix="/schedules",
    tags=["schedules"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=schemas.Schedule)
async def create_schedule(
    schedule: schemas.ScheduleCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return crud.create_schedule(db=db, schedule=schedule, user_id=current_user.id)

@router.get("/", response_model=List[schemas.Schedule])
async def read_schedules(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return crud.get_schedules(db, user_id=current_user.id, skip=skip, limit=limit)

@router.get("/{schedule_id}", response_model=schemas.Schedule)
async def read_schedule(
    schedule_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_schedule = crud.get_schedule(db, schedule_id=schedule_id, user_id=current_user.id)
    if db_schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )
    return db_schedule

@router.put("/{schedule_id}", response_model=schemas.Schedule)
async def update_schedule(
    schedule_id: int,
    schedule: schemas.ScheduleUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_schedule = crud.update_schedule(
        db, 
        schedule_id=schedule_id, 
        schedule=schedule, 
        user_id=current_user.id
    )
    if db_schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )
    return db_schedule

@router.delete("/{schedule_id}", response_model=schemas.Schedule)
async def delete_schedule(
    schedule_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_schedule = crud.delete_schedule(db, schedule_id=schedule_id, user_id=current_user.id)
    if db_schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )
    return db_schedule
