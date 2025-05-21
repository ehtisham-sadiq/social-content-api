from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, DateTime, Table, Enum, JSON, Index, func
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base

# Association table for post tags
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
    Index("ix_post_tags_post_id", "post_id"),
    Index("ix_post_tags_tag_id", "tag_id")
)

class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # LinkedIn integration
    linkedin_access_token = Column(String, nullable=True)
    linkedin_refresh_token = Column(String, nullable=True)
    linkedin_token_expires_at = Column(DateTime, nullable=True)
    linkedin_profile_id = Column(String, nullable=True)
    
    # Relationships
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    templates = relationship("Template", back_populates="author", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="user", cascade="all, delete-orphan")

    # Add indexes for frequently queried columns
    __table_args__ = (
        Index('ix_users_email_is_active', 'email', 'is_active'),
    )

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(Text)
    image_url = Column(String, nullable=True)
    status = Column(Enum(PostStatus), default=PostStatus.DRAFT)
    scheduled_time = Column(DateTime, nullable=True)
    published_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # LinkedIn specific fields
    linkedin_post_id = Column(String, nullable=True)
    linkedin_share_url = Column(String, nullable=True)
    
    # Foreign keys
    author_id = Column(Integer, ForeignKey("users.id"))
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    
    # Relationships
    author = relationship("User", back_populates="posts")
    template = relationship("Template", back_populates="posts")
    tags = relationship("Tag", secondary=post_tags, back_populates="posts")
    analytics = relationship("Analytics", back_populates="post", cascade="all, delete-orphan", uselist=False)

    # Add indexes for frequently queried columns and combinations
    __table_args__ = (
        Index('ix_posts_author_id_status', 'author_id', 'status'),
        Index('ix_posts_scheduled_time', 'scheduled_time'),
        Index('ix_posts_status', 'status'),
        Index('ix_posts_created_at', 'created_at'),
    )

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    
    # Relationships
    posts = relationship("Post", secondary=post_tags, back_populates="tags")

class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    content = Column(Text)
    category = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    author_id = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    author = relationship("User", back_populates="templates")
    posts = relationship("Post", back_populates="template")

    # Add indexes for frequently queried columns
    __table_args__ = (
        Index('ix_templates_author_id_category', 'author_id', 'category'),
    )

class Analytics(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, index=True)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    engagement_rate = Column(Integer, default=0)  # Stored as percentage * 100 for precision
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced = Column(DateTime, nullable=True)
    
    # Foreign keys
    post_id = Column(Integer, ForeignKey("posts.id"), unique=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    post = relationship("Post", back_populates="analytics")
    
    # Add indexes
    __table_args__ = (
        Index('ix_analytics_user_id', 'user_id'),
    )

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    schedule_type = Column(String)  # e.g., "evenly_spaced", "specific_days", "optimal_times"
    schedule_config = Column(JSON)  # Flexible configuration based on schedule_type
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    user = relationship("User", back_populates="schedules")

    # Add indexes
    __table_args__ = (
        Index('ix_schedules_user_id', 'user_id'),
    )
