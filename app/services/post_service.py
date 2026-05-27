import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.user_post import UserPost
from app.models.publish_job import PublishJob
from app.models.user import User
from app.models.draft import Draft


class PostService:

    async def create_and_dispatch(
        self,
        db: Session,
        user: User,
        draft: Draft,
        platforms: list,
        caption: str,
        image_urls: list,
        scheduled_time=None,
    ) -> list:
        """
        Create UserPost record + PublishJob per platform.
        Dispatch immediately if no scheduled_time.
        """
        from app.workers.scheduled_post_worker import execute_publish_job

        primary_url = image_urls[0] if image_urls else ""
        post_type = "carousel" if len(image_urls) > 1 else "single"

        # Check if post already exists for this draft — reuse it
        existing_post = None
        if draft:
            existing_post = (
                db.query(UserPost)
                .filter(UserPost.id == draft.post_id)
                .first()
            ) if draft.post_id else None

        # Determine post_type from draft
        draft_post_type = (draft.extracted_data or {}).get("post_type", "post")
        has_video = any(
            url and any(ext in url.lower() for ext in [".mp4", ".mov", "video"])
            for url in image_urls
        )
        if has_video and draft_post_type == "post":
            draft_post_type = "video"

        if existing_post:
            post = existing_post
            print(f"REUSING existing post {post.id} for draft {draft.id}")
        else:
            post = UserPost(
            user_id=user.id,
            post_type=draft_post_type,
            post_platform_type="scheduled" if scheduled_time else "immediate",
            caption=caption,
            url_list=image_urls,
            status="pending",
            scheduled_time=scheduled_time,
            )
            db.add(post)
            db.flush()
            # Save post_id to draft
            if draft:
                draft.post_id = post.id
                db.commit()

        # Check which platforms already have a successful job for this draft
        already_done = set()
        if draft:
            existing_jobs = (
                db.query(PublishJob)
                .filter(
                    PublishJob.draft_id == draft.id,
                    PublishJob.status == "done",
                )
                .all()
            )
            already_done = {j.platform for j in existing_jobs}
            if already_done:
                print(f"SKIPPING already posted platforms: {already_done}")

        jobs = []
        for platform in platforms:
            if platform in already_done:
                print(f"SKIP {platform} — already posted successfully")
                continue

            job = PublishJob(
                user_id=user.id,
                post_id=post.id,
                draft_id=draft.id,
                platform=platform,
                status="pending",
                scheduled_time=scheduled_time,
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            if not scheduled_time:
                execute_publish_job.delay(str(job.id))
                print(f"DISPATCHED job={job.id} platform={platform}")

            jobs.append(job)
        print(f"POST CREATED: {post.id} | {len(jobs)} jobs")
        return jobs


post_service = PostService()