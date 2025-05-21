import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.database import SessionLocal
from app import models, linkedin_api
from app.config import settings
from app.logger import logger
import time
import signal
import sys
from typing import Dict, Any, List

# Flag to control worker loop
running = True

async def process_scheduled_posts():
    """
    Process posts that are scheduled to be published
    """
    logger.info("Processing scheduled posts")
    
    # Create database session
    db = SessionLocal()
    try:
        # Get posts scheduled for the next 5 minutes
        now = datetime.utcnow()
        window_end = now + timedelta(minutes=5)
        
        scheduled_posts = db.query(models.Post).filter(
            and_(
                models.Post.status == models.PostStatus.SCHEDULED,
                models.Post.scheduled_time <= window_end,
                models.Post.scheduled_time > now - timedelta(minutes=5)  # Avoid reprocessing old posts
            )
        ).all()
        
        if not scheduled_posts:
            logger.info("No posts scheduled for publishing")
            return
        
        logger.info(f"Found {len(scheduled_posts)} posts to publish")
        
        # Process each post
        for post in scheduled_posts:
            try:
                # Get user
                user = db.query(models.User).filter(models.User.id == post.author_id).first()
                if not user:
                    logger.error(f"User not found for post {post.id}")
                    continue
                
                # Check if user has LinkedIn credentials
                if not user.linkedin_access_token:
                    logger.error(f"User {user.id} has no LinkedIn access token")
                    post.status = models.PostStatus.FAILED
                    db.commit()
                    continue
                
                # Check if token is expired and refresh if needed
                if user.linkedin_token_expires_at and user.linkedin_token_expires_at <= now:
                    if not user.linkedin_refresh_token:
                        logger.error(f"LinkedIn token expired for user {user.id} and no refresh token available")
                        post.status = models.PostStatus.FAILED
                        db.commit()
                        continue
                    
                    # Refresh token
                    try:
                        token_data = linkedin_api.refresh_access_token(user.linkedin_refresh_token)
                        user.linkedin_access_token = token_data["access_token"]
                        user.linkedin_refresh_token = token_data.get("refresh_token", user.linkedin_refresh_token)
                        user.linkedin_token_expires_at = now + timedelta(seconds=token_data["expires_in"])
                        db.commit()
                        logger.info(f"Refreshed LinkedIn token for user {user.id}")
                    except Exception as e:
                        logger.error(f"Failed to refresh LinkedIn token for user {user.id}: {str(e)}")
                        post.status = models.PostStatus.FAILED
                        db.commit()
                        continue
                
                # Initialize LinkedIn API client
                linkedin_client = linkedin_api.LinkedInAPI(user.linkedin_access_token)
                
                # Publish post
                if post.image_url:
                    # Post with image
                    response = linkedin_client.create_image_post(
                        author_id=user.linkedin_profile_id,
                        text=post.content,
                        image_url=post.image_url
                    )
                else:
                    # Text-only post
                    response = linkedin_client.create_text_post(
                        author_id=user.linkedin_profile_id,
                        text=post.content
                    )
                
                # Update post status
                post.status = models.PostStatus.PUBLISHED
                post.published_time = now
                post.linkedin_post_id = response.get("id", "")
                post.linkedin_share_url = response.get("shareUrl", "")
                db.commit()
                
                logger.info(f"Successfully published post {post.id} to LinkedIn")
                
                # Create initial analytics record
                analytics = db.query(models.Analytics).filter(models.Analytics.post_id == post.id).first()
                if not analytics:
                    analytics = models.Analytics(
                        post_id=post.id,
                        user_id=user.id,
                        last_synced=now
                    )
                    db.add(analytics)
                    db.commit()
            
            except Exception as e:
                logger.error(f"Error publishing post {post.id}: {str(e)}", exc_info=True)
                post.status = models.PostStatus.FAILED
                db.commit()
    
    except Exception as e:
        logger.error(f"Error in process_scheduled_posts: {str(e)}", exc_info=True)
    
    finally:
        db.close()

async def sync_post_analytics():
    """
    Sync analytics data from LinkedIn for published posts
    """
    logger.info("Syncing post analytics")
    
    # Create database session
    db = SessionLocal()
    try:
        # Get posts that need analytics sync
        # Prioritize recently published posts and posts that haven't been synced recently
        now = datetime.utcnow()
        one_day_ago = now - timedelta(days=1)
        one_week_ago = now - timedelta(days=7)
        
        # Query for posts to sync
        posts_to_sync = db.query(models.Post).filter(
            and_(
                models.Post.status == models.PostStatus.PUBLISHED,
                models.Post.linkedin_post_id.isnot(None),
                or_(
                    # Recently published posts
                    models.Post.published_time >= one_day_ago,
                    # Posts with analytics that haven't been synced in a day
                    and_(
                        models.Post.analytics.has(models.Analytics.last_synced <= one_day_ago),
                        models.Post.published_time >= one_week_ago
                    )
                )
            )
        ).limit(20).all()  # Limit to avoid overloading the API
        
        if not posts_to_sync:
            logger.info("No posts to sync analytics for")
            return
        
        logger.info(f"Found {len(posts_to_sync)} posts to sync analytics for")
        
        # Group posts by user to minimize API calls
        posts_by_user = {}
        for post in posts_to_sync:
            if post.author_id not in posts_by_user:
                posts_by_user[post.author_id] = []
            posts_by_user[post.author_id].append(post)
        
        # Process each user's posts
        for user_id, posts in posts_by_user.items():
            try:
                # Get user
                user = db.query(models.User).filter(models.User.id == user_id).first()
                if not user or not user.linkedin_access_token:
                    logger.error(f"User {user_id} has no LinkedIn access token")
                    continue
                
                # Check if token is expired and refresh if needed
                if user.linkedin_token_expires_at and user.linkedin_token_expires_at <= now:
                    if not user.linkedin_refresh_token:
                        logger.error(f"LinkedIn token expired for user {user_id} and no refresh token available")
                        continue
                    
                    # Refresh token
                    try:
                        token_data = linkedin_api.refresh_access_token(user.linkedin_refresh_token)
                        user.linkedin_access_token = token_data["access_token"]
                        user.linkedin_refresh_token = token_data.get("refresh_token", user.linkedin_refresh_token)
                        user.linkedin_token_expires_at = now + timedelta(seconds=token_data["expires_in"])
                        db.commit()
                        logger.info(f"Refreshed LinkedIn token for user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to refresh LinkedIn token for user {user_id}: {str(e)}")
                        continue
                
                # Initialize LinkedIn API client
                linkedin_client = linkedin_api.LinkedInAPI(user.linkedin_access_token)
                
                # Sync analytics for each post
                for post in posts:
                    try:
                        # Get analytics from LinkedIn
                        analytics_data = linkedin_client.get_post_analytics(post.linkedin_post_id)
                        
                        # Update or create analytics record
                        analytics = db.query(models.Analytics).filter(models.Analytics.post_id == post.id).first()
                        if not analytics:
                            analytics = models.Analytics(
                                post_id=post.id,
                                user_id=user_id
                            )
                            db.add(analytics)
                        
                        # Update analytics data
                        analytics.likes = analytics_data.get("likes", 0)
                        analytics.comments = analytics_data.get("comments", 0)
                        analytics.shares = analytics_data.get("shares", 0)
                        
                        # Calculate engagement rate
                        total_engagement = analytics.likes + analytics.comments + analytics.shares
                        if analytics.impressions > 0:
                            analytics.engagement_rate = int((total_engagement / analytics.impressions) * 10000)  # Store as percentage * 100
                        
                        analytics.last_synced = now
                        db.commit()
                        
                        logger.info(f"Successfully synced analytics for post {post.id}")
                    
                    except Exception as e:
                        logger.error(f"Error syncing analytics for post {post.id}: {str(e)}")
            
            except Exception as e:
                logger.error(f"Error processing posts for user {user_id}: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error in sync_post_analytics: {str(e)}", exc_info=True)
    
    finally:
        db.close()

async def worker_loop():
    """
    Main worker loop that runs scheduled tasks
    """
    logger.info("Starting worker loop")
    
    while running:
        try:
            # Process scheduled posts
            await process_scheduled_posts()
            
            # Sync post analytics
            await sync_post_analytics()
            
            # Sleep for a while
            await asyncio.sleep(60)  # Check every minute
        
        except Exception as e:
            logger.error(f"Error in worker loop: {str(e)}", exc_info=True)
            await asyncio.sleep(10)  # Sleep briefly before retrying

def handle_signal(sig, frame):
    """Handle termination signals"""
    global running
    logger.info(f"Received signal {sig}, shutting down worker")
    running = False

def start_worker():
    """Start the worker process"""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Start worker loop
    asyncio.run(worker_loop())

if __name__ == "__main__":
    start_worker()
