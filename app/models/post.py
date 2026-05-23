from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base


class Post(Base):

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    prompt = Column(Text)
    caption = Column(Text)
    image_url = Column(String)   # primary image (kept for backward compat)
    status = Column(String, default="draft")
    scheduled_time = Column(DateTime)
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="posts")
    publish_jobs = relationship("PublishJob", back_populates="post")
    images = relationship(
        "PostImage",
        back_populates="post",
        order_by="PostImage.position",
        cascade="all, delete-orphan",
    )