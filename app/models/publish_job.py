import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base


class PublishJob(Base):
    __tablename__ = "publish_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    post_id = Column(UUID(as_uuid=True), ForeignKey("user_posts.id"), nullable=False)
    draft_id = Column(UUID(as_uuid=True), ForeignKey("drafts.id"), nullable=True)
    platform = Column(String, nullable=False)
    status = Column(String, default="pending")     # pending | done | failed
    scheduled_time = Column(DateTime)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("UserPost", back_populates="publish_jobs")