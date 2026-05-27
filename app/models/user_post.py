import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base


class UserPost(Base):
    __tablename__ = "user_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform_type = Column(String)          # instagram, linkedin, etc.
    post_type = Column(String)              # single, carousel, video
    post_platform_type = Column(String)     # immediate, scheduled
    caption = Column(Text)
    url_list = Column(JSON, default=[])     # list of image/video URLs
    status = Column(String, default="draft")  # draft, published, failed, scheduled
    scheduled_time = Column(DateTime)
    published_at = Column(DateTime)
    credits_used = Column(Integer, default=0)
    failure_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="posts")
    publish_jobs = relationship("PublishJob", back_populates="post")