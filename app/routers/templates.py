from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app import crud, models, schemas
from app.database import get_db
from app.auth import get_current_active_user

router = APIRouter(
    prefix="/templates",
    tags=["templates"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=schemas.Template)
async def create_template(
    template: schemas.TemplateCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return crud.create_template(db=db, template=template, user_id=current_user.id)

@router.get("/", response_model=List[schemas.Template])
async def read_templates(
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    templates = crud.get_templates(
        db, 
        user_id=current_user.id,
        category=category,
        skip=skip, 
        limit=limit
    )
    return templates

@router.get("/{template_id}", response_model=schemas.Template)
async def read_template(
    template_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_template = crud.get_template(db, template_id=template_id)
    if db_template is None or db_template.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    return db_template

@router.put("/{template_id}", response_model=schemas.Template)
async def update_template(
    template_id: int,
    template: schemas.TemplateUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_template = crud.update_template(
        db, 
        template_id=template_id, 
        template=template, 
        user_id=current_user.id
    )
    if db_template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    return db_template

@router.delete("/{template_id}", response_model=schemas.Template)
async def delete_template(
    template_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_template = crud.delete_template(db, template_id=template_id, user_id=current_user.id)
    if db_template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    return db_template
