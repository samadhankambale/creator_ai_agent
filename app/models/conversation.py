from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey
)

from app.database.base import Base

class Conversation(Base):

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    state = Column(
        String,
        default="idle"
    )

    pending_post_id = Column(
        Integer,
        nullable=True
    )