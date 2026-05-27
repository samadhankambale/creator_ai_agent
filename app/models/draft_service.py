"""
DraftService — the single source of truth for user progress.

Every user action calls update_draft() which persists immediately to DB.
This ensures users can always resume from exactly where they left off.

Flow steps:
  entity_extraction → image_count → image_generation →
  image_selection → caption_review → platform_selection →
  schedule_input → ready_to_post → publishing → done
"""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.draft import Draft
from app.models.user import User


class DraftService:

    # ── Create ────────────────────────────────────────

    def create_draft(self, db: Session, user: User) -> Draft:
        """Create a new active draft for the user."""
        # Mark any existing active drafts as superseded
        existing = self.get_active_draft(db, str(user.id))
        # Don't auto-discard — let user choose to resume or discard

        draft = Draft(
            user_id=user.id,
            current_step="entity_extraction",
            draft_status="active",
            extracted_data={},
            generated_assets={
                "image_prompt": "",
                "generated_images": [],
                "selected_images": [],
                "caption": "",
                "edited_caption": None,
            },
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        print(f"DRAFT CREATED: {draft.id}")
        return draft

    # ── Read ──────────────────────────────────────────

    def get_active_draft(self, db: Session, user_id: str) -> Draft | None:
        """Get the user's current active draft."""
        return (
            db.query(Draft)
            .filter(
                Draft.user_id == user_id,
                Draft.draft_status == "active",
            )
            .order_by(Draft.created_at.desc())
            .first()
        )

    def get_draft_by_id(self, db: Session, draft_id: str) -> Draft | None:
        return db.query(Draft).filter(Draft.id == draft_id).first()

    # ── Update ────────────────────────────────────────

    def update_step(self, db: Session, draft: Draft, step: str) -> Draft:
        """Move draft to next step and auto-save."""
        draft.current_step = step
        draft.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(draft)
        print(f"DRAFT {draft.id} → step: {step}")
        return draft

    def update_extracted_data(
        self, db: Session, draft: Draft, data: dict
    ) -> Draft:
        """Merge extracted entities into draft. Auto-saves."""
        existing = dict(draft.extracted_data or {})
        existing.update({k: v for k, v in data.items() if v is not None})
        draft.extracted_data = existing
        draft.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(draft)
        return draft

    def update_generated_assets(
        self, db: Session, draft: Draft, assets: dict
    ) -> Draft:
        """Merge generated assets into draft. Auto-saves."""
        existing = dict(draft.generated_assets or {})
        existing.update({k: v for k, v in assets.items() if v is not None})
        draft.generated_assets = existing
        draft.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(draft)
        return draft

    def set_caption(self, db: Session, draft: Draft, caption: str) -> Draft:
        return self.update_generated_assets(db, draft, {"caption": caption})

    def set_edited_caption(self, db: Session, draft: Draft, caption: str) -> Draft:
        return self.update_generated_assets(db, draft, {"edited_caption": caption})

    def set_generated_images(self, db: Session, draft: Draft, urls: list) -> Draft:
        return self.update_generated_assets(db, draft, {"generated_images": urls})

    def set_selected_images(self, db: Session, draft: Draft, urls: list) -> Draft:
        return self.update_generated_assets(db, draft, {"selected_images": urls})

    def set_image_prompt(self, db: Session, draft: Draft, prompt: str) -> Draft:
        return self.update_generated_assets(db, draft, {"image_prompt": prompt})

    def set_platforms(self, db: Session, draft: Draft, platforms: list) -> Draft:
        return self.update_extracted_data(db, draft, {"platforms": platforms})

    def set_schedule(self, db: Session, draft: Draft, schedule_time) -> Draft:
        return self.update_extracted_data(db, draft, {"scheduled_time": str(schedule_time)})

    def set_image_count(self, db: Session, draft: Draft, count: int) -> Draft:
        return self.update_extracted_data(db, draft, {"image_count": count})

    # ── Status changes ────────────────────────────────

    def mark_completed(self, db: Session, draft: Draft, post_id=None) -> Draft:
        draft.draft_status = "completed"
        draft.current_step = "done"
        draft.completed_at = datetime.utcnow()
        if post_id:
            draft.post_id = post_id
        draft.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(draft)
        print(f"DRAFT {draft.id} COMPLETED")
        return draft

    def mark_failed(self, db: Session, draft: Draft, reason: str) -> Draft:
        draft.draft_status = "failed"
        draft.failure_reason = reason
        draft.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(draft)
        return draft

    def mark_discarded(self, db: Session, draft: Draft) -> Draft:
        draft.draft_status = "discarded"
        draft.discarded_at = datetime.utcnow()
        draft.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(draft)
        print(f"DRAFT {draft.id} DISCARDED")
        return draft

    def mark_publishing(self, db: Session, draft: Draft) -> Draft:
        return self.update_step(db, draft, "publishing")

    # ── Helpers ───────────────────────────────────────

    def get_missing_fields(self, draft: Draft) -> list:
        """Return list of required fields not yet collected."""
        data = draft.extracted_data or {}
        assets = draft.generated_assets or {}
        missing = []

        if not data.get("topic"):
            missing.append("topic")
        if not data.get("image_count"):
            missing.append("image_count")
        if not assets.get("selected_images"):
            missing.append("images")
        if not assets.get("caption") and not assets.get("edited_caption"):
            missing.append("caption")
        if not data.get("platforms"):
            missing.append("platforms")

        return missing

    def get_effective_caption(self, draft: Draft) -> str:
        """Return edited caption if exists, else generated caption."""
        assets = draft.generated_assets or {}
        return assets.get("edited_caption") or assets.get("caption") or ""

    def get_progress_summary(self, draft: Draft) -> str:
        """Human-readable summary of current draft progress."""
        data = draft.extracted_data or {}
        assets = draft.generated_assets or {}

        lines = ["*Current progress:*"]

        if data.get("topic"):
            lines.append(f"📝 Topic: {data['topic']}")
        if assets.get("selected_images"):
            count = len(assets["selected_images"])
            lines.append(f"🖼 Images selected: {count}")
        elif assets.get("generated_images"):
            count = len(assets["generated_images"])
            lines.append(f"🎨 Images generated: {count} (not yet selected)")
        if assets.get("caption") or assets.get("edited_caption"):
            lines.append("✍️ Caption: ready")
        if data.get("platforms"):
            platforms = " + ".join(p.title() for p in data["platforms"])
            lines.append(f"📱 Platforms: {platforms}")
        if data.get("scheduled_time"):
            lines.append(f"🕐 Scheduled: {data['scheduled_time']}")

        return "\n".join(lines)


draft_service = DraftService()