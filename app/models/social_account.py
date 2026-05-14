from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Boolean,
    DateTime
)

from sqlalchemy.orm import (
    relationship
)

from datetime import datetime

from app.database.base import Base


class SocialAccount(Base):

    __tablename__ = "social_accounts"

    id = Column(
        Integer,
        primary_key=True
    )

    user_id = Column(

        Integer,

        ForeignKey("users.id")
    )

    platform = Column(
        String,
        nullable=False
    )

    username = Column(String)

    access_token = Column(
        String,
        nullable=False
    )

    refresh_token = Column(
        String
    )

    platform_user_id = Column(
        String
    )

    token_expires_at = Column(
        DateTime
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # ==================================================
    # RELATIONSHIPS
    # ==================================================

    user = relationship(

        "User",

        back_populates=
        "social_accounts"
    )