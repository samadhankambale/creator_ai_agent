import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    parent_convo_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    session_id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    message_role = Column(String, nullable=False)   # user | assistant
    message_type = Column(String)                   # text | image | button
    current_message = Column(Text)
    summary_content = Column(Text)
    token_count = Column(Integer, default=0)
    total_session_tokens = Column(Integer, default=0)
    model_used = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="conversations")