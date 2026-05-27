from app.models.user import User  # noqa
from app.models.user_post import UserPost  # noqa
from app.models.user_social_account import UserSocialAccount  # noqa
from app.models.publish_job import PublishJob  # noqa
from app.models.draft import Draft  # noqa

from app.workers.celery_worker import celery_app
from app.database.session import SessionLocal
from app.services.social_account_service import social_account_service
from app.services.publishing_service import publishing_service, CAROUSEL_SUPPORTED
from app.integrations.whatsapp.whatsapp_client import send_message_sync


def _get_connect_url(whatsapp_number: str, platform: str) -> str | None:
    from app.core.config import settings
    base = settings.APP_BASE_URL
    return {
        "instagram": f"{base}/oauth/meta/connect?whatsapp_number={whatsapp_number}",
        "linkedin":  f"{base}/oauth/linkedin/connect?whatsapp_number={whatsapp_number}",
        "threads":   f"{base}/oauth/threads/connect?whatsapp_number={whatsapp_number}",
        "twitter":   f"{base}/oauth/twitter/connect?whatsapp_number={whatsapp_number}",
    }.get(platform)


def _is_auth_error(details) -> bool:
    """
    Return True only for genuine token expiry / auth errors.
    """
    d = str(details or "").lower()

    # Explicit non-auth codes — check first before anything else
    non_auth_codes = ["100", "9004", "2207052", "2207067"]
    for code in non_auth_codes:
        if f'"code": {code}' in str(details) or f"'code': {code}" in str(details):
            return False

    # Instagram/Threads token expiry
    if '"code": 190' in str(details) or "'code': 190" in str(details):
        return True
    if "session has expired" in d:
        return True

    # LinkedIn token expiry
    if '"status": 401' in str(details) or '"status":401' in str(details):
        return True
    if "expired_token" in d or "revoked_token" in d:
        return True

    # Twitter token expiry
    if "unsupported authentication" in d:
        return True
    if "unauthorized" in d and "oauth" in d:
        return True

    # Generic 401
    if '"status_code": 401' in str(details) or "'status_code': 401" in str(details):
        return True

    return False


def _friendly_error(platform: str, details) -> str:
    details_str = str(details or "")
    dl = details_str.lower()

    # Instagram specific errors
    if platform == "instagram":
        if "190" in details_str or "session has expired" in dl:
            return "Instagram session expired. Please reconnect your Instagram account."
        if "unsupported media type" in dl or "2207067" in details_str:
            return "This media type is not supported for the selected post format on Instagram."
        if "media could not be fetched" in dl or "2207052" in details_str:
            return "Instagram could not access the media. The file may be too large or in wrong format."
        if "video" in dl and "processing" in dl:
            return "Video is still processing. Please try again in a few minutes."

    # Twitter
    if platform == "twitter":
        if "creditsdepleted" in dl or "credits" in dl:
            return "Twitter posting is temporarily unavailable. Please try again later."
        if "401" in details_str or "unauthorized" in dl or "unsupported authentication" in dl:
            return "Twitter session expired. Please reconnect your Twitter account."

    # LinkedIn
    if platform == "linkedin":
        if "401" in details_str or "unauthorized" in dl or "expired_token" in dl or "revoked_token" in dl:
            return "LinkedIn session expired. Please reconnect your LinkedIn account."

    # Threads
    if platform == "threads":
        if "190" in details_str or "session has expired" in dl:
            return "Threads session expired. Please reconnect your Threads account."
        if "500 characters" in dl:
            return "Caption too long for Threads (max 500 characters)."

    return f"Something went wrong posting to {platform.title()}. Error: {details_str[:100]}"

def _check_and_send_summary(db, draft_id, whatsapp_number: str):
    """
    Check if all jobs for this draft are complete.
    If yes — send ONE final summary message.
    If not — wait for remaining jobs to finish.
    """
    all_jobs = (
        db.query(PublishJob)
        .filter(PublishJob.draft_id == draft_id)
        .all()
    )

    if not all_jobs:
        return

    # Check if any jobs are still pending
    pending = [j for j in all_jobs if j.status == "pending"]
    if pending:
        print(f"SUMMARY: {len(pending)} jobs still pending, waiting...")
        return

    # All jobs done — build summary
    succeeded = [j for j in all_jobs if j.status == "done"]
    failed = [j for j in all_jobs if j.status == "failed"]

    print(f"SUMMARY: {len(succeeded)} succeeded, {len(failed)} failed")

    # Build clean summary
    if succeeded and not failed:
        platforms_str = " + ".join(j.platform.title() for j in succeeded)
        message = f"🎉 Posted on {platforms_str}!\n\nWhat would you like to do next? Send me a new topic to create another post."

    elif succeeded and failed:
        success_str = " + ".join(j.platform.title() for j in succeeded)
        fail_str = " + ".join(j.platform.title() for j in failed)
        # Add reconnect links for auth errors
        reconnect_lines = []
        for j in failed:
            if _is_auth_error(j.error_message or ""):
                url = _get_connect_url(whatsapp_number, j.platform)
                if url:
                    reconnect_lines.append(f"🔗 {j.platform.title()}: {url}")
        reconnect = ("\n" + "\n".join(reconnect_lines)) if reconnect_lines else ""
        message = (
            f"✅ {success_str} — posted\n"
            f"❌ {fail_str} — failed{reconnect}\n\n"
            f"Send *retry* to retry."
        )

    else:
        # All failed
        reconnect_lines = []
        for j in failed:
            if _is_auth_error(j.error_message or ""):
                url = _get_connect_url(whatsapp_number, j.platform)
                if url:
                    reconnect_lines.append(f"🔗 {j.platform.title()}: {url}")
        reconnect = ("\n" + "\n".join(reconnect_lines)) if reconnect_lines else ""
        message = f"❌ Could not post.{reconnect}\n\nSend *retry* to try again."

    send_message_sync(whatsapp_number, message)



@celery_app.task(name="app.workers.scheduled_post_worker.execute_publish_job")
def execute_publish_job(job_id: str):
    db = SessionLocal()

    try:
        print("=" * 40)
        print(f"EXECUTING JOB: {job_id}")
        print("=" * 40)

        job = db.query(PublishJob).filter(PublishJob.id == job_id).first()
        if not job:
            print(f"JOB {job_id} NOT FOUND")
            return

        if job.status != "pending":
            print(f"JOB {job_id} already {job.status}, skipping")
            return

        post = db.query(UserPost).filter(UserPost.id == job.post_id).first()
        if not post:
            job.status = "failed"
            job.error_message = "Post not found"
            db.commit()
            return

        user = db.query(User).filter(User.id == job.user_id).first()

        account = social_account_service.get_decrypted(db, job.user_id, job.platform)
        print(f"ACCOUNT FOUND: {bool(account)}")
        if account:
            token_preview = account.access_token[:20] if account.access_token else "None"
            print(f"TOKEN PREVIEW: {token_preview}...")
            print(f"PLATFORM USER ID: {account.platform_user_id}")
        if account:
            print(f"PLATFORM USER ID: {account.platform_user_id}")
            print(f"TOKEN LENGTH: {len(account.access_token) if account.access_token else 0}")
            print(f"TOKEN PREFIX: {account.access_token[:20] if account.access_token else 'NONE'}")
        if not account:
            job.status = "failed"
            job.error_message = f"{job.platform} not connected"
            db.commit()
            if user:
                connect_url = _get_connect_url(user.number, job.platform)
                send_message_sync(
                    user.number,
                    f"⚠️ {job.platform.title()} is not connected.\n\nTap to connect:\n{connect_url}"
                )
            return

        # Get all images from post
        image_urls = post.url_list or []
        primary_image = image_urls[0] if image_urls else ""
        extra_images = image_urls[1:] if len(image_urls) > 1 else []
        total_images = len(image_urls)

        print(f"PLATFORM: {job.platform} | IMAGES: {total_images}")

        # Warn if carousel not supported
        if total_images > 1 and job.platform not in CAROUSEL_SUPPORTED:
            if user:
                send_message_sync(
                    user.number,
                    f"ℹ️ {job.platform.title()} doesn't support multiple images — "
                    "posting first image only."
                )

        # Get post_type and video_url from post metadata
        url_list = post.url_list or []

        # Re-upload Pollinations URLs to Cloudinary (Instagram rejects direct Pollinations URLs)
        fixed_urls = []
        for url in url_list:
            if url and "pollinations.ai" in url:
                try:
                    import requests as _req
                    from app.integrations.cloudinary_client import upload_media
                    print(f"RE-UPLOADING Pollinations URL...")
                    resp = _req.get(url, timeout=20)  # 20s timeout
                    if resp.status_code == 200:
                        public_url = upload_media(resp.content, "image", "reupload")
                        print(f"RE-UPLOADED: {public_url}")
                        fixed_urls.append(public_url)
                    else:
                        print(f"Pollinations download failed {resp.status_code} — skipping")
                        fixed_urls.append(url)
                except Exception as _e:
                    print(f"RE-UPLOAD ERROR: {_e} — using original URL")
                    fixed_urls.append(url)
            else:
                fixed_urls.append(url)
        url_list = fixed_urls

        video_url = None
        image_urls = []
        for url in url_list:
            if url and any(x in url.lower() for x in [
                ".mp4", ".mov", ".avi", ".webm",
                "/video/upload/",   # Cloudinary video URL
                "video_url",        # explicit video marker
            ]):
                video_url = url
            else:
                image_urls.append(url)

        primary_image = image_urls[0] if image_urls else (url_list[0] if url_list else "")
        extra_images = image_urls[1:] if len(image_urls) > 1 else []
        post_type = getattr(post, "post_type", "post") or "post"
        # Normalize post_type
        if post_type in ("single", "carousel"):
            post_type = "post"
        # If video present and post_type is just "post", treat as video post
        if video_url and post_type == "post":
            post_type = "video"
        print(f"RESOLVED POST TYPE: {post_type} | has_video={bool(video_url)}")

        result = publishing_service.publish(
            platform=job.platform,
            access_token=account.access_token,
            platform_user_id=account.platform_user_id,
            caption=post.caption,
            image_url=primary_image,
            extra_image_urls=extra_images if extra_images else None,
            video_url=video_url,
            post_type=post_type,
        )

        print(f"PUBLISH RESULT: {result}")

        # Handle skip cases (not errors, just unsupported features)
        if not result.get("success") and result.get("skip_reconnect"):
            job.status = "failed"
            job.error_message = result.get("details", "")
            db.commit()
            if user:
                send_message_sync(
                    user.number,
                    f"ℹ️ {job.platform.title()}: {result.get('error', 'Not supported')}."
                )
            return

        if result.get("success"):
            job.status = "done"
            job.completed_at = __import__("datetime").datetime.utcnow()
            post.status = "published"
            post.published_at = __import__("datetime").datetime.utcnow()
            db.commit()
        else:
            error = result.get("error", "Unknown error")
            details = result.get("details", "")
            job.status = "failed"
            job.error_message = f"{error}: {details}"
            db.commit()

            # Mark draft as failed so user can retry
            if job.draft_id:
                from app.models.draft import Draft
                draft_obj = db.query(Draft).filter(Draft.id == job.draft_id).first()
                if draft_obj and draft_obj.draft_status in ("completed", "active"):
                    draft_obj.draft_status = "failed"
                    draft_obj.current_step = "ready_to_post"
                    draft_obj.failure_reason = f"{error}: {details}"
                    db.commit()

        # Check if all jobs for this draft are now complete
        if job.draft_id and user:
            _check_and_send_summary(db, job.draft_id, user.number)

    except Exception as e:
        print(f"WORKER EXCEPTION for job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        try:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


@celery_app.task(name="app.workers.scheduled_post_worker.run_scheduled_jobs")
@celery_app.task(name="app.workers.scheduled_post_worker.run_scheduled_jobs")
def run_scheduled_jobs():
    from datetime import datetime
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        print(f"BEAT: checking at UTC {now}")

        # Debug: show all pending scheduled jobs
        all_pending = (
            db.query(PublishJob)
            .filter(
                PublishJob.status == "pending",
                PublishJob.scheduled_time != None,
            )
            .all()
        )
        for j in all_pending:
            print(f"  PENDING JOB: {j.id} platform={j.platform} scheduled={j.scheduled_time} due={j.scheduled_time <= now}")

        # Cancel stale jobs older than 24h (stuck due to timezone bug)
        from datetime import timedelta
        stale_cutoff = now - timedelta(hours=24)
        stale = (
            db.query(PublishJob)
            .filter(
                PublishJob.status == "pending",
                PublishJob.scheduled_time != None,
                PublishJob.scheduled_time < stale_cutoff,
            )
            .all()
        )
        for j in stale:
            j.status = "failed"
            j.error_message = "Expired — scheduled time passed"
            print(f"CANCELLED stale job {j.id} platform={j.platform}")
        if stale:
            db.commit()

        due_jobs = (
            db.query(PublishJob)
            .filter(
                PublishJob.status == "pending",
                PublishJob.scheduled_time <= now,
                PublishJob.scheduled_time != None,
            )
            .all()
        )
        print(f"BEAT: {len(due_jobs)} scheduled jobs due")
        for job in due_jobs:
            execute_publish_job.delay(str(job.id))
    except Exception as e:
        print(f"BEAT ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()