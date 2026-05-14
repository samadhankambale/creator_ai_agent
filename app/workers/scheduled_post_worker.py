from datetime import datetime

from app.workers.celery_worker import (
    celery_app
)

from app.database.session import (
    SessionLocal
)

from app.repositories.publish_job_repository import (
    publish_job_repository
)

from app.repositories.post_repository import (
    post_repository
)

from app.services.social_account_service import (
    social_account_service
)

from app.services.publishing_service import (
    publishing_service
)


# ======================================================
# PROCESS PUBLISH JOB
# ======================================================

@celery_app.task(
    bind=True,
    max_retries=3
)
def process_publish_job(
    self,
    job_id: int
):

    db = SessionLocal()

    try:

        # ------------------------------------------------
        # GET JOB
        # ------------------------------------------------

        jobs = (
            publish_job_repository
            .get_pending_jobs(db)
        )

        job = next(
            (
                j for j in jobs
                if j.id == job_id
            ),
            None
        )

        if not job:

            return {
                "error":
                "Job not found"
            }

        # ------------------------------------------------
        # UPDATE STATUS
        # ------------------------------------------------

        publish_job_repository.update_job_status(

            db=db,

            job_id=job.id,

            status="processing"
        )

        # ------------------------------------------------
        # GET POST
        # ------------------------------------------------

        post = (
            post_repository
            .get_post_by_id(
                db,
                job.post_id
            )
        )

        if not post:

            publish_job_repository.update_job_status(

                db=db,

                job_id=job.id,

                status="failed",

                error_message=
                "Post not found"
            )

            return

        # ------------------------------------------------
        # GET USER
        # ------------------------------------------------

        user = (
            social_account_service
            .get_user_by_whatsapp(
                db,
                post.user.whatsapp_number
            )
        )

        if not user:

            publish_job_repository.update_job_status(

                db=db,

                job_id=job.id,

                status="failed",

                error_message=
                "User not found"
            )

            return

        # ------------------------------------------------
        # GET ACCOUNT
        # ------------------------------------------------

        account = (
            social_account_service
            .get_connected_account(

                db=db,

                whatsapp_number=
                user.whatsapp_number,

                platform=
                job.platform
            )
        )

        if not account:

            publish_job_repository.update_job_status(

                db=db,

                job_id=job.id,

                status="failed",

                error_message=
                f"{job.platform} account not connected"
            )

            return

        # ------------------------------------------------
        # PUBLISH
        # ------------------------------------------------

        result = (
            publishing_service
            .publish_post(

                platform=
                job.platform,

                caption=
                post.caption,

                image_url=
                post.image_url,

                account=
                account
            )
        )

        # ------------------------------------------------
        # SUCCESS
        # ------------------------------------------------

        publish_job_repository.update_job_status(

            db=db,

            job_id=job.id,

            status="success"
        )

        post_repository.update_post_status(

            db=db,

            post_id=post.id,

            status="published"
        )

        return result

    except Exception as e:

        publish_job_repository.update_job_status(

            db=db,

            job_id=job_id,

            status="failed",

            error_message=str(e)
        )

        raise self.retry(
            exc=e,
            countdown=60
        )

    finally:

        db.close()


# ======================================================
# PROCESS SCHEDULED JOBS
# ======================================================

@celery_app.task
def process_scheduled_jobs():

    db = SessionLocal()

    try:

        jobs = (
            publish_job_repository
            .get_pending_jobs(db)
        )

        now = datetime.now()

        for job in jobs:

            # --------------------------------------------
            # IMMEDIATE JOB
            # --------------------------------------------

            if not job.scheduled_time:

                process_publish_job.delay(
                    job.id
                )

                continue

            # --------------------------------------------
            # SCHEDULED JOB
            # --------------------------------------------

            if job.scheduled_time <= now:

                process_publish_job.delay(
                    job.id
                )

    finally:

        db.close()