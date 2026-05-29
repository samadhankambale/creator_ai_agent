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

        # Detect if any URL is a video (Cloudinary video or common video extension)
        def is_video_url(url: str) -> bool:
            if not url:
                return False
            u = url.lower()
            return any(x in u for x in [
                ".mp4", ".mov", ".avi", ".webm",
                "/video/upload/",   # Cloudinary video
            ])

        has_video = any(is_video_url(u) for u in image_urls)

        # Determine post_type
        draft_post_type = (draft.extracted_data or {}).get("post_type", "post") if draft else "post"
        if has_video:
            draft_post_type = "video"
        elif len(image_urls) > 1:
            draft_post_type = "carousel"

        print(f"POST SERVICE: has_video={has_video} post_type={draft_post_type} urls={image_urls}")

        # Check if post already exists for this draft — reuse it
        existing_post = None
        if draft and draft.post_id:
            existing_post = db.query(UserPost).filter(UserPost.id == draft.post_id).first()

        if existing_post:
            # Update url_list and caption in case they changed
            existing_post.url_list = image_urls
            existing_post.caption = caption
            existing_post.post_type = draft_post_type
            if scheduled_time:
                existing_post.scheduled_time = scheduled_time
            db.commit()
            post = existing_post
            print(f"REUSING post {post.id} — updated url_list")
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
            if draft:
                draft.post_id = post.id
                db.commit()

        # Check which platforms already succeeded for this draft
        already_done = set()
        if draft:
            existing_jobs = (
                db.query(PublishJob)
                .filter(PublishJob.draft_id == draft.id, PublishJob.status == "done")
                .all()
            )
            already_done = {j.platform for j in existing_jobs}
            if already_done:
                print(f"SKIPPING already posted: {already_done}")

        jobs = []
        for platform in platforms:
            if platform in already_done:
                print(f"SKIP {platform} — already posted successfully")
                continue

            job = PublishJob(
                user_id=user.id,
                post_id=post.id,
                draft_id=draft.id if draft else None,
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

        print(f"POST CREATED: {post.id} | {len(jobs)} jobs | urls={image_urls}")
        return jobs


post_service = PostService()