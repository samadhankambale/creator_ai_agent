import re
from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.user_repository import user_repository
from app.repositories.post_repository import post_repository
from app.repositories.publish_job_repository import publish_job_repository
from app.repositories.social_account_repository import social_account_repository
from app.integrations.groq.groq_client import generate_caption
from app.integrations.image_provider import generate_images


class PostService:

    # ── Caption ───────────────────────────────────────

    async def generate_caption_only(self, user_message: str) -> str:
        topic = self._clean_topic(user_message)
        return await generate_caption(topic)

    def build_image_prompt(self, user_message: str) -> str:
        topic = self._clean_topic(user_message)
        return (
            f"aesthetic social media background for: {topic}, "
            "minimal, high quality, vibrant"
        )

    def _clean_topic(self, text: str) -> str:
        cleaned = re.sub(
            r"\b(generate|create|make|give me|show|produce)?\s*"
            r"(\d+|one|two|three|four)\s*(image|images|img|photos?)?\b",
            "", text, flags=re.IGNORECASE
        ).strip(" ,.")
        return cleaned if cleaned else text

    # ── Image generation ──────────────────────────────

    def generate_multiple_images(self, prompt: str, count: int) -> list:
        return generate_images(prompt, count)

    # ── Save post with all images ─────────────────────

    def save_post_with_images(
        self,
        db: Session,
        whatsapp_number: str,
        user_message: str,
        caption: str,
        image_urls: list,
    ) -> dict:
        """
        Save post + all images to DB using post_images table.
        Returns pending_post dict for session storage.
        """
        user = user_repository.get_or_create(db, whatsapp_number)
        primary = image_urls[0] if image_urls else ""
        extras = image_urls[1:] if len(image_urls) > 1 else []

        post = post_repository.create(
            db=db,
            user_id=user.id,
            prompt=user_message,
            caption=caption,
            image_url=primary,
            extra_image_urls=extras,
        )

        print(f"POST SAVED: id={post.id} images={len(image_urls)}")

        return {
            "post_id": post.id,
            "caption": caption,
            "image_url": primary,
            "extra_image_urls": extras,
            "platforms": [],
        }

    # ── Platform auth check ───────────────────────────

    def get_missing_platforms(
        self,
        db: Session,
        whatsapp_number: str,
        platforms: list,
    ) -> list:
        user = user_repository.get_by_whatsapp(db, whatsapp_number)
        if not user:
            return platforms

        missing = [
            p for p in platforms
            if not social_account_repository.get(db, user.id, p)
        ]
        print("CONNECTED:", [p for p in platforms if p not in missing])
        print("MISSING:", missing)
        return missing

    # ── Immediate publish ─────────────────────────────

    def create_immediate_publish_jobs(
        self,
        db: Session,
        whatsapp_number: str,
        pending_post: dict,
        platforms: list,
    ) -> list:
        from app.workers.scheduled_post_worker import execute_publish_job

        user = user_repository.get_or_create(db, whatsapp_number)
        post_id = pending_post.get("post_id")

        print(f"DISPATCHING JOBS: post_id={post_id} platforms={platforms}")

        jobs = []
        for platform in platforms:
            job = publish_job_repository.create(
                db=db,
                user_id=user.id,
                post_id=post_id,
                platform=platform,
                scheduled_time=None,
            )
            execute_publish_job.delay(job.id)
            print(f"DISPATCHED job_id={job.id} platform={platform}")
            jobs.append(job)

        return jobs

    # ── Scheduled publish ─────────────────────────────

    def create_scheduled_publish_jobs(
        self,
        db: Session,
        whatsapp_number: str,
        pending_post: dict,
        platforms: list,
        scheduled_time: datetime,
    ) -> list:
        user = user_repository.get_or_create(db, whatsapp_number)
        post_id = pending_post.get("post_id")

        jobs = []
        for platform in platforms:
            job = publish_job_repository.create(
                db=db,
                user_id=user.id,
                post_id=post_id,
                platform=platform,
                scheduled_time=scheduled_time,
            )
            print(f"SCHEDULED job_id={job.id} platform={platform} at={scheduled_time}")
            jobs.append(job)

        return jobs


post_service = PostService()