from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import random

from app import models, schemas
from app.auth import get_password_hash

# User CRUD operations
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user: schemas.UserUpdate):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None
    
    update_data = user.dict(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None
    db.delete(db_user)
    db.commit()
    return db_user

# Post CRUD operations
def get_post(db: Session, post_id: int):
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def get_posts(
    db: Session, 
    user_id: Optional[int] = None,
    status: Optional[models.PostStatus] = None,
    skip: int = 0, 
    limit: int = 100
):
    query = db.query(models.Post)
    if user_id:
        query = query.filter(models.Post.author_id == user_id)
    if status:
        query = query.filter(models.Post.status == status)
    return query.order_by(desc(models.Post.created_at)).offset(skip).limit(limit).all()

def create_post(db: Session, post: schemas.PostCreate, user_id: int):
    # Handle tags
    tags = []
    if post.tags:
        for tag_name in post.tags:
            tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.add(tag)
                db.flush()
            tags.append(tag)
    
    # Create post
    db_post = models.Post(
        title=post.title,
        content=post.content,
        image_url=post.image_url,
        scheduled_time=post.scheduled_time,
        template_id=post.template_id,
        author_id=user_id,
        tags=tags
    )
    
    # Set status based on scheduled time
    if post.scheduled_time:
        db_post.status = models.PostStatus.SCHEDULED
    
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

def update_post(db: Session, post_id: int, post: schemas.PostUpdate, user_id: int):
    db_post = db.query(models.Post).filter(
        models.Post.id == post_id,
        models.Post.author_id == user_id
    ).first()
    
    if not db_post:
        return None
    
    # Update post fields
    update_data = post.dict(exclude_unset=True)
    
    # Handle tags if provided
    if "tags" in update_data:
        tags = []
        for tag_name in update_data.pop("tags"):
            tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.add(tag)
                db.flush()
            tags.append(tag)
        db_post.tags = tags
    
    # Update status based on scheduled time if provided
    if "scheduled_time" in update_data and update_data["scheduled_time"]:
        update_data["status"] = models.PostStatus.SCHEDULED
    
    for key, value in update_data.items():
        setattr(db_post, key, value)
    
    db.commit()
    db.refresh(db_post)
    return db_post

def delete_post(db: Session, post_id: int, user_id: int):
    db_post = db.query(models.Post).filter(
        models.Post.id == post_id,
        models.Post.author_id == user_id
    ).first()
    
    if not db_post:
        return None
    
    db.delete(db_post)
    db.commit()
    return db_post

def publish_post(db: Session, post_id: int, user_id: int, linkedin_post_id: str, linkedin_share_url: str):
    db_post = db.query(models.Post).filter(
        models.Post.id == post_id,
        models.Post.author_id == user_id
    ).first()
    
    if not db_post:
        return None
    
    db_post.status = models.PostStatus.PUBLISHED
    db_post.published_time = datetime.utcnow()
    db_post.linkedin_post_id = linkedin_post_id
    db_post.linkedin_share_url = linkedin_share_url
    
    db.commit()
    db.refresh(db_post)
    return db_post

# Template CRUD operations
def get_template(db: Session, template_id: int):
    return db.query(models.Template).filter(models.Template.id == template_id).first()

def get_templates(
    db: Session, 
    user_id: Optional[int] = None,
    category: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100
):
    query = db.query(models.Template)
    if user_id:
        query = query.filter(models.Template.author_id == user_id)
    if category:
        query = query.filter(models.Template.category == category)
    return query.order_by(desc(models.Template.created_at)).offset(skip).limit(limit).all()

def create_template(db: Session, template: schemas.TemplateCreate, user_id: int):
    db_template = models.Template(
        name=template.name,
        content=template.content,
        category=template.category,
        author_id=user_id
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def update_template(db: Session, template_id: int, template: schemas.TemplateUpdate, user_id: int):
    db_template = db.query(models.Template).filter(
        models.Template.id == template_id,
        models.Template.author_id == user_id
    ).first()
    
    if not db_template:
        return None
    
    update_data = template.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_template, key, value)
    
    db.commit()
    db.refresh(db_template)
    return db_template

def delete_template(db: Session, template_id: int, user_id: int):
    db_template = db.query(models.Template).filter(
        models.Template.id == template_id,
        models.Template.author_id == user_id
    ).first()
    
    if not db_template:
        return None
    
    db.delete(db_template)
    db.commit()
    return db_template

# Analytics CRUD operations
def get_post_analytics(db: Session, post_id: int, user_id: int):
    return db.query(models.Analytics).filter(
        models.Analytics.post_id == post_id,
        models.Analytics.user_id == user_id
    ).first()

def get_user_analytics(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Analytics).filter(
        models.Analytics.user_id == user_id
    ).offset(skip).limit(limit).all()

def create_or_update_analytics(db: Session, analytics: schemas.AnalyticsUpdate, post_id: int, user_id: int):
    db_analytics = db.query(models.Analytics).filter(
        models.Analytics.post_id == post_id,
        models.Analytics.user_id == user_id
    ).first()
    
    if not db_analytics:
        # Create new analytics
        db_analytics = models.Analytics(
            post_id=post_id,
            user_id=user_id,
            **analytics.dict()
        )
        db.add(db_analytics)
    else:
        # Update existing analytics
        update_data = analytics.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_analytics, key, value)
    
    db.commit()
    db.refresh(db_analytics)
    return db_analytics

def get_analytics_summary(db: Session, user_id: int, days: int = 30):
    # Get date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get published posts in date range
    posts = db.query(models.Post).filter(
        models.Post.author_id == user_id,
        models.Post.status == models.PostStatus.PUBLISHED,
        models.Post.published_time >= start_date,
        models.Post.published_time <= end_date
    ).all()
    
    post_ids = [post.id for post in posts]
    
    # Get analytics for these posts
    analytics = db.query(models.Analytics).filter(
        models.Analytics.post_id.in_(post_ids)
    ).all()
    
    # Calculate summary
    total_impressions = sum(a.impressions for a in analytics)
    total_clicks = sum(a.clicks for a in analytics)
    total_likes = sum(a.likes for a in analytics)
    total_comments = sum(a.comments for a in analytics)
    total_shares = sum(a.shares for a in analytics)
    
    # Calculate engagement rate
    engagement_actions = total_likes + total_comments + total_shares
    engagement_rate = (engagement_actions / total_impressions) * 100 if total_impressions > 0 else 0
    
    # Get best performing post
    best_post = None
    best_engagement = 0
    
    for post in posts:
        post_analytics = next((a for a in analytics if a.post_id == post.id), None)
        if post_analytics:
            post_engagement = post_analytics.likes + post_analytics.comments + post_analytics.shares
            if post_engagement > best_engagement:
                best_engagement = post_engagement
                best_post = post
    
    return {
        "total_posts": len(posts),
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "engagement_rate": engagement_rate,
        "best_performing_post": best_post.id if best_post else None
    }

# Schedule CRUD operations
def get_schedule(db: Session, schedule_id: int, user_id: int):
    return db.query(models.Schedule).filter(
        models.Schedule.id == schedule_id,
        models.Schedule.user_id == user_id
    ).first()

def get_schedules(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Schedule).filter(
        models.Schedule.user_id == user_id
    ).offset(skip).limit(limit).all()

def create_schedule(db: Session, schedule: schemas.ScheduleCreate, user_id: int):
    db_schedule = models.Schedule(
        name=schedule.name,
        schedule_type=schedule.schedule_type,
        schedule_config=schedule.schedule_config,
        user_id=user_id
    )
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

def update_schedule(db: Session, schedule_id: int, schedule: schemas.ScheduleUpdate, user_id: int):
    db_schedule = db.query(models.Schedule).filter(
        models.Schedule.id == schedule_id,
        models.Schedule.user_id == user_id
    ).first()
    
    if not db_schedule:
        return None
    
    update_data = schedule.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_schedule, key, value)
    
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

def delete_schedule(db: Session, schedule_id: int, user_id: int):
    db_schedule = db.query(models.Schedule).filter(
        models.Schedule.id == schedule_id,
        models.Schedule.user_id == user_id
    ).first()
    
    if not db_schedule:
        return None
    
    db.delete(db_schedule)
    db.commit()
    return db_schedule

# Bulk operations
def bulk_create_posts(db: Session, posts: List[schemas.PostCreate], user_id: int):
    created_posts = []
    for post in posts:
        created_post = create_post(db, post, user_id)
        created_posts.append(created_post)
    return created_posts

def bulk_schedule_posts(db: Session, post_ids: List[int], schedule_type: str, schedule_config: Dict[str, Any], user_id: int):
    # Get posts
    posts = db.query(models.Post).filter(
        models.Post.id.in_(post_ids),
        models.Post.author_id == user_id
    ).all()
    
    if not posts or len(posts) != len(post_ids):
        return None
    
    # Calculate schedule times based on schedule type
    schedule_times = []
    now = datetime.utcnow()
    
    if schedule_type == "evenly_spaced":
        # Schedule posts evenly across a time period
        start_date = datetime.fromisoformat(schedule_config.get("start_date"))
        end_date = datetime.fromisoformat(schedule_config.get("end_date"))
        time_slots = schedule_config.get("time_slots", ["09:00"])
        
        # Calculate days between start and end
        days_between = (end_date - start_date).days + 1
        posts_per_day = len(posts) / days_between
        
        # If posts_per_day <= len(time_slots), we can schedule multiple posts per day
        if posts_per_day <= len(time_slots):
            current_date = start_date
            time_slot_index = 0
            
            for post in posts:
                if current_date > end_date:
                    break
                
                # Get time from time slot
                time_parts = time_slots[time_slot_index].split(":")
                hour, minute = int(time_parts[0]), int(time_parts[1])
                
                # Create scheduled time
                scheduled_time = current_date.replace(hour=hour, minute=minute)
                schedule_times.append((post.id, scheduled_time))
                
                # Move to next time slot or next day
                time_slot_index += 1
                if time_slot_index >= len(time_slots):
                    time_slot_index = 0
                    current_date += timedelta(days=1)
        else:
            # We need to schedule posts across days
            days_per_post = days_between / len(posts)
            for i, post in enumerate(posts):
                day_offset = int(i * days_per_post)
                current_date = start_date + timedelta(days=day_offset)
                
                # Get time from time slot (use first time slot for simplicity)
                time_parts = time_slots[0].split(":")
                hour, minute = int(time_parts[0]), int(time_parts[1])
                
                # Create scheduled time
                scheduled_time = current_date.replace(hour=hour, minute=minute)
                schedule_times.append((post.id, scheduled_time))
    
    elif schedule_type == "specific_days":
        # Schedule posts on specific days of the week
        days = schedule_config.get("days", ["Monday"])
        time_slots = schedule_config.get("time_slots", ["09:00"])
        weeks_ahead = schedule_config.get("weeks_ahead", 4)
        
        # Map day names to weekday numbers (0 = Monday, 6 = Sunday)
        day_map = {
            "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
            "Friday": 4, "Saturday": 5, "Sunday": 6
        }
        
        # Convert day names to weekday numbers
        weekdays = [day_map[day] for day in days if day in day_map]
        
        # Generate all possible dates
        possible_dates = []
        current_date = now.date()
        end_date = current_date + timedelta(days=7 * weeks_ahead)
        
        while current_date <= end_date:
            if current_date.weekday() in weekdays:
                for time_slot in time_slots:
                    time_parts = time_slot.split(":")
                    hour, minute = int(time_parts[0]), int(time_parts[1])
                    scheduled_time = datetime.combine(current_date, datetime.min.time())
                    scheduled_time = scheduled_time.replace(hour=hour, minute=minute)
                    if scheduled_time > now:
                        possible_dates.append(scheduled_time)
            current_date += timedelta(days=1)
        
        # Assign posts to dates
        for i, post in enumerate(posts):
            if i < len(possible_dates):
                schedule_times.append((post.id, possible_dates[i]))
    
    elif schedule_type == "optimal_times":
        # Schedule posts at optimal times based on analytics
        # This is a simplified version - in a real app, you'd analyze past performance
        optimal_hours = [9, 12, 17, 20]  # Example optimal hours
        days_ahead = schedule_config.get("days_ahead", 14)
        
        # Generate schedule
        current_date = now.date()
        post_index = 0
        
        for day in range(days_ahead):
            for hour in optimal_hours:
                if post_index >= len(posts):
                    break
                    
                scheduled_time = datetime.combine(current_date, datetime.min.time())
                scheduled_time = scheduled_time.replace(hour=hour, minute=0)
                
                if scheduled_time > now:
                    schedule_times.append((posts[post_index].id, scheduled_time))
                    post_index += 1
            
            current_date += timedelta(days=1)
            if post_index >= len(posts):
                break
    
    # Update posts with scheduled times
    for post_id, scheduled_time in schedule_times:
        post = next((p for p in posts if p.id == post_id), None)
        if post:
            post.scheduled_time = scheduled_time
            post.status = models.PostStatus.SCHEDULED
    
    db.commit()
    
    # Return schedule preview
    return [{"post_id": post_id, "scheduled_time": scheduled_time} for post_id, scheduled_time in schedule_times]
