from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app import crud, models, schemas
from app.database import get_db
from app.auth import get_current_active_user

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses={404: {"description": "Not found"}},
)

@router.get("/posts/{post_id}", response_model=schemas.Analytics)
async def read_post_analytics(
    post_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Check if post exists and belongs to user
    post = crud.get_post(db, post_id=post_id)
    if post is None or post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    # Get analytics
    analytics = crud.get_post_analytics(db, post_id=post_id, user_id=current_user.id)
    if analytics is None:
        # Create empty analytics if none exists
        analytics = crud.create_or_update_analytics(
            db, 
            analytics=schemas.AnalyticsUpdate(), 
            post_id=post_id, 
            user_id=current_user.id
        )
    
    return analytics

@router.put("/posts/{post_id}", response_model=schemas.Analytics)
async def update_post_analytics(
    post_id: int,
    analytics: schemas.AnalyticsUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Check if post exists and belongs to user
    post = crud.get_post(db, post_id=post_id)
    if post is None or post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    # Update analytics
    return crud.create_or_update_analytics(
        db, 
        analytics=analytics, 
        post_id=post_id, 
        user_id=current_user.id
    )

@router.get("/summary", response_model=Dict[str, Any])
async def get_analytics_summary(
    days: int = 30,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return crud.get_analytics_summary(db, user_id=current_user.id, days=days)

@router.get("/", response_model=List[schemas.AnalyticsWithPost])
async def read_user_analytics(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return crud.get_user_analytics(db, user_id=current_user.id, skip=skip, limit=limit)
