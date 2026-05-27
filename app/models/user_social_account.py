import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base


class UserSocialAccount(Base):
    __tablename__ = "user_social_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform_type = Column(String, nullable=False)  # instagram, linkedin, threads, twitter
    username = Column(String)
    api_key = Column(String)
    api_secret = Column(String)
    access_token = Column(String)
    access_token_secret = Column(String)
    token_expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # platform_user_id stored in api_key field for OAuth2 platforms
    @property
    def platform_user_id(self):
        return self.api_key

    @platform_user_id.setter
    def platform_user_id(self, value):
        self.api_key = value

    user = relationship("User", back_populates="social_accounts")