# Must be first — loads all models into SQLAlchemy registry
from app.models.user import User  # noqa: F401
from app.models.post import Post  # noqa: F401
from app.models.post_image import PostImage  # noqa: F401
from app.models.social_account import SocialAccount  # noqa: F401
from app.models.publish_job import PublishJob  # noqa: F401

from app.workers.celery_worker import celery_app
from app.database.session import SessionLocal
from app.repositories.publish_job_repository import publish_job_repository
from app.repositories.post_repository import post_repository
from app.repositories.social_account_repository import social_account_repository
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
    """Check if the error is an authentication/token expiry error."""
    if isinstance(details, dict):
        details = str(details)
    details = (details or "").lower()
    return any(x in details for x in [
        "190", "oauthexception", "session has expired",
        "401", "unauthorized", "invalid token",
        "token expired", "access token"
    ])


def _friendly_error(platform: str, details) -> str:
    if isinstance(details, dict):
        details = str(details)
    details = details or ""
    dl = details.lower()

    if platform == "twitter":
        if "creditsdepleted" in dl or "credits" in dl:
            return "Twitter posting is temporarily unavailable. Please try again later."
        if "401" in details or "unauthorized" in dl:
            return "Twitter session expired. Please reconnect your Twitter account."

    if platform == "instagram":
        if "190" in details or "oauthexception" in dl:
            return "Instagram session expired. Please reconnect your Instagram account."

    if platform == "linkedin":
        if "401" in details or "unauthorized" in dl:
            return "LinkedIn session expired. Please reconnect your LinkedIn account."

    if platform == "threads":
        if "190" in details or "session has expired" in dl or "oauthexception" in dl:
            return "Threads session expired. Please reconnect your Threads account."

    return f"Something went wrong posting to {platform.title()}. Please try again."


@celery_app.task(name="app.workers.scheduled_post_worker.execute_publish_job")
def execute_publish_job(job_id: int):
    db = SessionLocal()

    try:
        print("=" * 40)
        print(f"EXECUTING JOB: {job_id}")
        print("=" * 40)

        job = publish_job_repository.get_by_id(db, job_id)
        if not job:
            print(f"JOB {job_id} NOT FOUND")
            return

        if job.status != "pending":
            print(f"JOB {job_id} already {job.status}, skipping")
            return

        post = post_repository.get_by_id(db, job.post_id)
        if not post:
            publish_job_repository.mark_failed(db, job_id, "Post not found")
            return

        user = db.query(User).filter(User.id == job.user_id).first()

        account = social_account_repository.get_decrypted(db, job.user_id, job.platform)
        if not account:
            publish_job_repository.mark_failed(db, job_id, f"{job.platform} not connected")
            if user:
                connect_url = _get_connect_url(user.whatsapp_number, job.platform)
                send_message_sync(
                    user.whatsapp_number,
                    f"⚠️ {job.platform.title()} is not connected.\n\n"
                    f"Tap to connect:\n{connect_url}"
                )
            return

        # Get all images for carousel
        all_image_urls = post_repository.get_all_image_urls(db, job.post_id)
        primary_image = all_image_urls[0] if all_image_urls else post.image_url
        extra_images = all_image_urls[1:] if len(all_image_urls) > 1 else []
        total_images = len(all_image_urls)

        print(f"PLATFORM: {job.platform} | IMAGES: {total_images}")

        # Warn if platform doesn't support carousel
        if total_images > 1 and job.platform not in CAROUSEL_SUPPORTED:
            if user:
                send_message_sync(
                    user.whatsapp_number,
                    f"ℹ️ {job.platform.title()} doesn't support multiple images — "
                    "posting first image only."
                )

        result = publishing_service.publish(
            platform=job.platform,
            access_token=account.access_token,
            platform_user_id=account.platform_user_id,
            caption=post.caption,
            image_url=primary_image,
            extra_image_urls=extra_images if extra_images else None,
        )

        print(f"PUBLISH RESULT: {result}")

        if result.get("success"):
            publish_job_repository.mark_done(db, job_id)
            post_repository.update_status(db, post.id, "published")
            if user:
                img_info = f" ({total_images} images)" if total_images > 1 else ""
                send_message_sync(
                    user.whatsapp_number,
                    f"✅ Posted successfully to {job.platform.title()}{img_info}!"
                )
        else:
            error = result.get("error", "Unknown error")
            details = result.get("details", "")
            publish_job_repository.mark_failed(db, job_id, f"{error}: {details}")

            if user:
                friendly = _friendly_error(job.platform, details)
                connect_url = _get_connect_url(user.whatsapp_number, job.platform)

                # Always include reconnect link on auth errors
                if _is_auth_error(details) and connect_url:
                    msg = (
                        f"❌ Failed to post to {job.platform.title()}.\n\n"
                        f"{friendly}\n\n"
                        f"Tap to reconnect:\n{connect_url}"
                    )
                else:
                    msg = f"❌ Failed to post to {job.platform.title()}.\n\n{friendly}"

                send_message_sync(user.whatsapp_number, msg)

    except Exception as e:
        print(f"WORKER EXCEPTION for job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        try:
            publish_job_repository.mark_failed(db, job_id, str(e))
        except Exception:
            pass
    finally:
        db.close()


@celery_app.task(name="app.workers.scheduled_post_worker.run_scheduled_jobs")
def run_scheduled_jobs():
    db = SessionLocal()
    try:
        due_jobs = publish_job_repository.get_pending_due(db)
        print(f"BEAT: {len(due_jobs)} scheduled jobs due")
        for job in due_jobs:
            execute_publish_job.delay(job.id)
    except Exception as e:
        print(f"BEAT ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()