from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database.base import Base


class PostImage(Base):

    __tablename__ = "post_images"

    id = Column(Integer, primary_key=True)

    post_id = Column(
        Integer,
        ForeignKey("posts.id"),
        nullable=False,
    )

    url = Column(String, nullable=False)

    position = Column(Integer, default=0)  # order: 0 = primary

    post = relationship("Post", back_populates="images")