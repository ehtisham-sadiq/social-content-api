from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app import crud, models, schemas
from app.database import get_db
from app.auth import get_current_active_user

router = APIRouter(
    prefix="/bulk",
    tags=["bulk operations"],
    responses={404: {"description": "Not found"}},
)

@router.post("/posts", response_model=List[schemas.Post])
async def bulk_create_posts(
    bulk_posts: schemas.BulkPostCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return crud.bulk_create_posts(db=db, posts=bulk_posts.posts, user_id=current_user.id)

@router.post("/schedule", response_model=List[schemas.SchedulePreview])
async def bulk_schedule_posts(
    schedule_request: schemas.BulkScheduleRequest,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    schedule = crud.bulk_schedule_posts(
        db=db, 
        post_ids=schedule_request.post_ids, 
        schedule_type=schedule_request.schedule_type,
        schedule_config=schedule_request.schedule_config,
        user_id=current_user.id
    )
    
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid post IDs or schedule configuration"
        )
    
    return schedule
