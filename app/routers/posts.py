from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app import crud, models, schemas
from app.database import get_db
from app.auth import get_current_active_user
from app.models import PostStatus

router = APIRouter(
    prefix="/posts",
    tags=["posts"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=schemas.Post)
async def create_post(
    post: schemas.PostCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return crud.create_post(db=db, post=post, user_id=current_user.id)

@router.get("/", response_model=List[schemas.PostWithRelations])
async def read_posts(
    status: Optional[PostStatus] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    posts = crud.get_posts(
        db, 
        user_id=current_user.id,
        status=status,
        skip=skip, 
        limit=limit
    )
    return posts

@router.get("/{post_id}", response_model=schemas.PostWithRelations)
async def read_post(
    post_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_post = crud.get_post(db, post_id=post_id)
    if db_post is None or db_post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    return db_post

@router.put("/{post_id}", response_model=schemas.Post)
async def update_post(
    post_id: int,
    post: schemas.PostUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_post = crud.update_post(db, post_id=post_id, post=post, user_id=current_user.id)
    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    return db_post

@router.delete("/{post_id}", response_model=schemas.Post)
async def delete_post(
    post_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_post = crud.delete_post(db, post_id=post_id, user_id=current_user.id)
    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    return db_post

@router.post("/{post_id}/publish", response_model=schemas.Post)
async def publish_post(
    post_id: int,
    linkedin_post_id: str = Query(...),
    linkedin_share_url: str = Query(...),
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_post = crud.publish_post(
        db, 
        post_id=post_id, 
        user_id=current_user.id,
        linkedin_post_id=linkedin_post_id,
        linkedin_share_url=linkedin_share_url
    )
    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    return db_post
