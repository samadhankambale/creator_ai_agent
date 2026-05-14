from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Text
)

from sqlalchemy.orm import (
    relationship
)

from datetime import datetime

from app.database.base import Base


class PublishJob(Base):

    __tablename__ = "publish_jobs"

    id = Column(
        Integer,
        primary_key=True
    )

    user_id = Column(

        Integer,

        ForeignKey("users.id")
    )

    post_id = Column(

        Integer,

        ForeignKey("posts.id")
    )

    platform = Column(String)

    status = Column(

        String,

        default="pending"
    )

    scheduled_time = Column(
        DateTime
    )

    retry_count = Column(

        Integer,

        default=0
    )

    error_message = Column(
        Text
    )

    completed_at = Column(
        DateTime
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
        "publish_jobs"
    )

    post = relationship(

        "Post",

        back_populates=
        "publish_jobs"
    )