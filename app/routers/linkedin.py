from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import datetime, timedelta

from app import crud, models, schemas, linkedin_api
from app.database import get_db
from app.auth import get_current_active_user
from app.config import settings
from app.logger import logger

router = APIRouter(
    prefix="/linkedin",
    tags=["linkedin"],
    responses={404: {"description": "Not found"}},
)

@router.get("/auth-url")
async def get_auth_url(
    current_user: models.User = Depends(get_current_active_user)
):
    """Get LinkedIn OAuth authorization URL"""
    return {"auth_url": linkedin_api.get_linkedin_auth_url()}

@router.get("/callback")
async def linkedin_callback(
    code: str = Query(...),
    state: str = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Handle LinkedIn OAuth callback"""
    try:
        # Exchange code for token
        token_data = linkedin_api.exchange_code_for_token(code)
        
        # Update user with LinkedIn tokens
        current_user.linkedin_access_token = token_data["access_token"]
        current_user.linkedin_refresh_token = token_data.get("refresh_token")
        current_user.linkedin_token_expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        
        # Get LinkedIn profile ID
        linkedin_client = linkedin_api.LinkedInAPI(current_user.linkedin_access_token)
        profile_data = linkedin_client.get_profile()
        current_user.linkedin_profile_id = profile_data.get("id")
        
        db.commit()
        
        return {"message": "LinkedIn account connected successfully"}
    
    except Exception as e:
        logger.error(f"LinkedIn callback error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect LinkedIn account: {str(e)}"
        )

@router.post("/disconnect")
async def disconnect_linkedin(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Disconnect LinkedIn account"""
    current_user.linkedin_access_token = None
    current_user.linkedin_refresh_token = None
    current_user.linkedin_token_expires_at = None
    current_user.linkedin_profile_id = None
    
    db.commit()
    
    return {"message": "LinkedIn account disconnected successfully"}

@router.get("/status")
async def linkedin_status(
    current_user: models.User = Depends(get_current_active_user)
):
    """Get LinkedIn connection status"""
    is_connected = (
        current_user.linkedin_access_token is not None and
        current_user.linkedin_profile_id is not None
    )
    
    token_expired = False
    if current_user.linkedin_token_expires_at:
        token_expired = current_user.linkedin_token_expires_at <= datetime.utcnow()
    
    return {
        "is_connected": is_connected,
        "token_expired": token_expired,
        "profile_id": current_user.linkedin_profile_id if is_connected else None
    }

@router.post("/publish/{post_id}")
async def publish_to_linkedin(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Publish post to LinkedIn"""
    # Check if user has LinkedIn credentials
    if not current_user.linkedin_access_token or not current_user.linkedin_profile_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LinkedIn account not connected"
        )
    
    # Check if token is expired
    if current_user.linkedin_token_expires_at and current_user.linkedin_token_expires_at <= datetime.utcnow():
        if not current_user.linkedin_refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="LinkedIn token expired, please reconnect your account"
            )
        
        # Refresh token
        try:
            token_data = linkedin_api.refresh_access_token(current_user.linkedin_refresh_token)
            current_user.linkedin_access_token = token_data["access_token"]
            current_user.linkedin_refresh_token = token_data.get("refresh_token", current_user.linkedin_refresh_token)
            current_user.linkedin_token_expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
            db.commit()
        except Exception as e:
            logger.error(f"Failed to refresh LinkedIn token: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to refresh LinkedIn token, please reconnect your account"
            )
    
    # Get post
    post = crud.get_post(db, post_id=post_id)
    if not post or post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    # Check if post is already published
    if post.status == models.PostStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Post is already published"
        )
    
    try:
        # Initialize LinkedIn API client
        linkedin_client = linkedin_api.LinkedInAPI(current_user.linkedin_access_token)
        
        # Publish post
        if post.image_url:
            # Post with image
            response = linkedin_client.create_image_post(
                author_id=current_user.linkedin_profile_id,
                text=post.content,
                image_url=post.image_url
            )
        else:
            # Text-only post
            response = linkedin_client.create_text_post(
                author_id=current_user.linkedin_profile_id,
                text=post.content
            )
        
        # Update post status
        post.status = models.PostStatus.PUBLISHED
        post.published_time = datetime.utcnow()
        post.linkedin_post_id = response.get("id", "")
        post.linkedin_share_url = response.get("shareUrl", "")
        db.commit()
        
        # Create initial analytics record
        analytics = db.query(models.Analytics).filter(models.Analytics.post_id == post.id).first()
        if not analytics:
            analytics = models.Analytics(
                post_id=post.id,
                user_id=current_user.id,
                last_synced=datetime.utcnow()
            )
            db.add(analytics)
            db.commit()
        
        return {"message": "Post published to LinkedIn successfully", "post_id": post.id}
    
    except Exception as e:
        logger.error(f"Error publishing to LinkedIn: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish post to LinkedIn: {str(e)}"
        )
