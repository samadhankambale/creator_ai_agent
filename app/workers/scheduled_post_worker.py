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


@celery_app.task(
    bind=True,
    max_retries=3
)

@celery_app.task(
    name="app.workers.scheduled_post_worker.process_publish_job"
)
def process_publish_job(
    self,
    job_id
):

    db = SessionLocal()

    try:

        job = (
            publish_job_repository
            .get_job_by_id(
                db,
                job_id
            )
        )

        if not job:

            return

        post = (
            post_repository
            .get_post_by_id(
                db,
                job.post_id
            )
        )

        if not post:

            return

        account = (
            social_account_service
            .get_connected_account(

                db=db,

                whatsapp_number=
                post.user.whatsapp_number,

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
                "Account not connected"
            )

            return

        publish_job_repository.update_job_status(

            db=db,

            job_id=job.id,

            status="processing"
        )

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

        if result.get("success"):

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

        else:

            publish_job_repository.update_job_status(

                db=db,

                job_id=job.id,

                status="failed",

                error_message=
                str(result)
            )

    except Exception as e:

        print(e)

        raise self.retry(
            exc=e,
            countdown=60
        )

    finally:

        db.close()


@celery_app.task(
    name="app.workers.scheduled_post_worker.process_scheduled_jobs"
)
def process_scheduled_jobs():

    db = SessionLocal()

    try:

        jobs = (
            publish_job_repository
            .get_pending_jobs(db)
        )

        now = datetime.now()

        for job in jobs:

            if (
                job.scheduled_time
                and job.scheduled_time <= now
            ):

                process_publish_job.delay(
                    job.id
                )

    finally:

        db.close()