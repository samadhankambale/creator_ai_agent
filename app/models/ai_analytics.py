import uuid
from sqlalchemy import Column, String, Integer, DateTime, Numeric, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base


class AIAnalytics(Base):
    __tablename__ = "ai_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reference_id = Column(UUID(as_uuid=True))       # draft_id or post_id
    reference_type = Column(String)                  # draft | post
    type = Column(String, nullable=False)            # caption | image | extraction
    tokens_used = Column(Integer, default=0)
    model_used = Column(String)
    provider = Column(String)                        # groq | gemini | pollinations
    estimated_cost = Column(Numeric(10, 6), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="ai_analytics")