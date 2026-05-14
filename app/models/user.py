from sqlalchemy import (
    Column,
    Integer,
    String
)

from sqlalchemy.orm import (
    relationship
)

from app.database.base import Base


class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True
    )

    whatsapp_number = Column(

        String,

        unique=True,

        nullable=False
    )

    full_name = Column(String)

    timezone = Column(

        String,

        default="Asia/Kolkata"
    )

    # ==================================================
    # RELATIONSHIPS
    # ==================================================

    posts = relationship(

        "Post",

        back_populates="user"
    )

    social_accounts = relationship(

        "SocialAccount",

        back_populates="user"
    )

    publish_jobs = relationship(

        "PublishJob",

        back_populates="user"
    )