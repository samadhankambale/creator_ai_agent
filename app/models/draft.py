import uuid
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base


class Draft(Base):
    """
    Persistent draft that survives restarts, device switches, crashes.
    Auto-saved at every step so users can always resume.

    draft_status:
      active      — in progress
      completed   — successfully published
      discarded   — user explicitly discarded
      failed      — publish failed, awaiting retry

    current_step:
      entity_extraction  — extracting fields from first message
      image_count        — asking how many images
      image_generation   — generating images
      image_selection    — user picking images
      caption_review     — showing caption, awaiting proceed/edit
      platform_selection — user selecting platforms
      schedule_input     — user entering schedule time
      ready_to_post      — all set, showing Post Now / Schedule
      publishing         — currently publishing
    """

    __tablename__ = "drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    current_step = Column(String, default="entity_extraction")
    draft_status = Column(String, default="active")

    # Extracted entities from user's first message
    extracted_data = Column(JSON, default={})
    # {
    #   "topic": "egg recipe",
    #   "platforms": ["instagram"],
    #   "media_type": "carousel",
    #   "caption_instruction": "recipe details",
    #   "schedule": "tomorrow 8PM",
    #   "image_count": null,
    #   "tone": "motivational",
    #   "hashtags": [],
    #   "language": "english"
    # }

    # Generated content
    generated_assets = Column(JSON, default={})
    # {
    #   "image_prompt": "",
    #   "generated_images": [],   # all generated URLs
    #   "selected_images": [],    # user-picked URLs
    #   "caption": "",
    #   "edited_caption": null
    # }

    # Post reference after publishing
    post_id = Column(UUID(as_uuid=True), ForeignKey("user_posts.id"), nullable=True)

    # Failure tracking
    failure_reason = Column(Text)
    retry_count = Column(String, default="0")

    discarded_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="drafts")