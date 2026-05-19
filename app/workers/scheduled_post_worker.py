"""
IMPORTANT: All 4 models must be imported before any SQLAlchemy
query runs, so relationships (User, Post, etc.) resolve correctly.
"""

# ── Load all models first — DO NOT REMOVE THESE ──────────────
from app.models.user import User  # noqa: F401
from app.models.post import Post  # noqa: F401
from app.models.social_account import SocialAccount  # noqa: F401
from app.models.publish_job import PublishJob  # noqa: F401
# ─────────────────────────────────────────────────────────────

from app.workers.celery_worker import celery_app
from app.database.session import SessionLocal
from app.repositories.publish_job_repository import publish_job_repository
from app.repositories.post_repository import post_repository
from app.repositories.social_account_repository import social_account_repository
from app.services.publishing_service import publishing_service
from app.integrations.whatsapp.whatsapp_client import send_message_sync


# ──────────────────────────────────────────────────────────────
# TASK 1: Execute a single publish job
# ──────────────────────────────────────────────────────────────

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

        # ── Get post ──────────────────────────────────
        post = post_repository.get_by_id(db, job.post_id)
        if not post:
            publish_job_repository.mark_failed(db, job_id, "Post record not found")
            return

        # ── Get user for WhatsApp notifications ───────
        user = db.query(User).filter(User.id == job.user_id).first()

        # ── Get decrypted social account ──────────────
        account = social_account_repository.get_decrypted(
            db, job.user_id, job.platform
        )
        if not account:
            error = f"{job.platform} account not connected"
            publish_job_repository.mark_failed(db, job_id, error)
            if user:
                send_message_sync(
                    user.whatsapp_number,
                    f"❌ Could not post to {job.platform.title()}: account not connected."
                )
            return

        print(f"PLATFORM: {job.platform}")
        print(f"PLATFORM USER ID: {account.platform_user_id}")
        print(f"CAPTION: {post.caption[:80]}")
        print(f"IMAGE URL: {post.image_url}")

        # ── Publish ───────────────────────────────────
        result = publishing_service.publish(
            platform=job.platform,
            access_token=account.access_token,
            platform_user_id=account.platform_user_id,
            caption=post.caption,
            image_url=post.image_url,
        )

        print("PUBLISH RESULT:", result)

        if result.get("success"):
            publish_job_repository.mark_done(db, job_id)
            post_repository.update_status(db, post.id, "published")
            if user:
                send_message_sync(
                    user.whatsapp_number,
                    f"✅ Posted successfully to {job.platform.title()}!"
                )
        else:
            error = result.get("error", "Unknown error")
            details = result.get("details", "")
            publish_job_repository.mark_failed(db, job_id, f"{error}: {details}")
            if user:
                send_message_sync(
                    user.whatsapp_number,
                    f"❌ Failed to post to {job.platform.title()}.\n\nError: {error}"
                )

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


# ──────────────────────────────────────────────────────────────
# TASK 2: Beat — pick up scheduled jobs that are due
# ──────────────────────────────────────────────────────────────

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