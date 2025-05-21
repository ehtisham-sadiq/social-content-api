from pydantic import BaseModel, EmailStr, HttpUrl, validator, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import enum
from app.models import PostStatus

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None


class RefreshToken(BaseModel):
    refresh_token: str
# User schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None

class UserInDB(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class User(UserInDB):
    pass

# Tag schemas
class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int
    
    class Config:
        from_attributes = True

# Template schemas
class TemplateBase(BaseModel):
    name: str
    content: str
    category: Optional[str] = None

class TemplateCreate(TemplateBase):
    pass

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None

class Template(TemplateBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class TemplateWithAuthor(Template):
    author: User
    
    class Config:
        from_attributes = True

# Post schemas
class PostBase(BaseModel):
    title: str
    content: str
    image_url: Optional[HttpUrl] = None
    scheduled_time: Optional[datetime] = None
    template_id: Optional[int] = None

class PostCreate(PostBase):
    tags: Optional[List[str]] = []

class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[HttpUrl] = None
    status: Optional[PostStatus] = None
    scheduled_time: Optional[datetime] = None
    template_id: Optional[int] = None
    tags: Optional[List[str]] = None

class Post(PostBase):
    id: int
    status: PostStatus
    author_id: int
    published_time: Optional[datetime] = None
    linkedin_post_id: Optional[str] = None
    linkedin_share_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class PostWithRelations(Post):
    author: User
    template: Optional[Template] = None
    tags: List[Tag] = []
    
    class Config:
        from_attributes = True

# Analytics schemas
class AnalyticsBase(BaseModel):
    impressions: int = 0
    clicks: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    engagement_rate: float = 0.0
    data_points: List[Dict[str, Any]] = []

class AnalyticsCreate(AnalyticsBase):
    post_id: int

class AnalyticsUpdate(AnalyticsBase):
    pass

class Analytics(AnalyticsBase):
    id: int
    post_id: int
    user_id: int
    last_updated: datetime
    
    class Config:
        from_attributes = True

class AnalyticsWithPost(Analytics):
    post: Post
    
    class Config:
        from_attributes = True

# Schedule schemas
class ScheduleBase(BaseModel):
    name: str
    schedule_type: str
    schedule_config: Dict[str, Any]

class ScheduleCreate(ScheduleBase):
    pass

class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_config: Optional[Dict[str, Any]] = None

class Schedule(ScheduleBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Bulk operation schemas
class BulkPostCreate(BaseModel):
    posts: List[PostCreate]

class BulkScheduleRequest(BaseModel):
    post_ids: List[int]
    schedule_type: str
    schedule_config: Dict[str, Any]

class SchedulePreview(BaseModel):
    post_id: int
    scheduled_time: datetime

class BulkScheduleResponse(BaseModel):
    schedule: List[SchedulePreview]
