import uuid
from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    number = Column(String, unique=True, nullable=False)  # whatsapp number
    email = Column(String)
    password = Column(String)
    is_active = Column(Boolean, default=True)
    preferences = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    social_accounts = relationship("UserSocialAccount", back_populates="user")
    posts = relationship("UserPost", back_populates="user")
    drafts = relationship("Draft", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")
    subscription = relationship("UserSubscription", back_populates="user", uselist=False)
    orders = relationship("Order", back_populates="user")
    ai_analytics = relationship("AIAnalytics", back_populates="user")