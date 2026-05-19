from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.user_repository import user_repository
from app.repositories.post_repository import post_repository
from app.repositories.publish_job_repository import publish_job_repository
from app.repositories.social_account_repository import social_account_repository
from app.integrations.groq.groq_client import generate_caption
from app.integrations.pollinations.pollinations_client import generate_image


class PostService:

    # ── AI post generation ────────────────────────────

    async def create_ai_post(
        self,
        db: Session,
        whatsapp_number: str,
        user_message: str,
    ) -> dict:

        print("=" * 40)
        print("CREATING AI POST")
        print("USER MESSAGE:", user_message)
        print("=" * 40)

        caption_prompt = (
            f"Create a viral social media caption for this topic: {user_message}\n"
            "Make it engaging, motivational, and include 3-5 hashtags."
        )
        image_prompt = (
            f"aesthetic social media background for: {user_message}, "
            "minimal, high quality, vibrant"
        )

        caption = await generate_caption(caption_prompt)
        image_url = await generate_image(image_prompt)

        print("IMAGE URL:", image_url)

        user = user_repository.get_or_create(db, whatsapp_number)
        post = post_repository.create(
            db=db,
            user_id=user.id,
            prompt=user_message,
            caption=caption,
            image_url=image_url,
        )

        return {
            "post_id": post.id,
            "caption": caption,
            "image_url": image_url,
            "platforms": [],
        }

    # ── Platform auth check ───────────────────────────

    def get_missing_platforms(
        self,
        db: Session,
        whatsapp_number: str,
        platforms: list,
    ) -> list:

        print("=" * 40)
        print("CHECKING MISSING PLATFORMS")
        print("WHATSAPP NUMBER:", whatsapp_number)
        print("PLATFORMS:", platforms)
        print("=" * 40)

        user = user_repository.get_by_whatsapp(db, whatsapp_number)
        if not user:
            print("USER NOT FOUND — all platforms missing")
            return platforms

        connected = []
        missing = []
        for platform in platforms:
            account = social_account_repository.get(db, user.id, platform)
            if account:
                connected.append(platform)
            else:
                missing.append(platform)

        print("CONNECTED PLATFORMS:", connected)
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

        # Import here to avoid circular imports at module load time
        from app.workers.scheduled_post_worker import execute_publish_job

        user = user_repository.get_or_create(db, whatsapp_number)
        post_id = pending_post.get("post_id")

        print("=" * 40)
        print("CREATING IMMEDIATE JOBS")
        print("POST ID:", post_id)
        print("PLATFORMS:", platforms)
        print("=" * 40)

        jobs = []
        for platform in platforms:
            job = publish_job_repository.create(
                db=db,
                user_id=user.id,
                post_id=post_id,
                platform=platform,
                scheduled_time=None,
            )

            print(f"DISPATCHING JOB: job_id={job.id} platform={platform}")

            # Use .delay() directly — most reliable way to dispatch on Windows
            execute_publish_job.delay(job.id)

            print(f"JOB DISPATCHED: job_id={job.id}")
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

        from app.workers.scheduled_post_worker import execute_publish_job

        user = user_repository.get_or_create(db, whatsapp_number)
        post_id = pending_post.get("post_id")

        print("=" * 40)
        print("CREATING SCHEDULED JOBS")
        print("POST ID:", post_id)
        print("PLATFORMS:", platforms)
        print("SCHEDULED TIME:", scheduled_time)
        print("=" * 40)

        jobs = []
        for platform in platforms:
            job = publish_job_repository.create(
                db=db,
                user_id=user.id,
                post_id=post_id,
                platform=platform,
                scheduled_time=scheduled_time,
            )
            print(f"SCHEDULED JOB CREATED: job_id={job.id} platform={platform} at={scheduled_time}")
            jobs.append(job)

        return jobs


post_service = PostService()