from app.models.publish_job import (
    PublishJob
)


class PublishJobRepository:

    # ==================================================
    # CREATE JOB
    # ==================================================

    def create_job(
        self,
        db,
        user_id,
        post_id,
        platform,
        scheduled_time=None
    ):

        job = PublishJob(

            user_id=user_id,

            post_id=post_id,

            platform=platform,

            scheduled_time=scheduled_time,

            status="pending"
        )

        db.add(job)

        db.commit()

        db.refresh(job)

        return job

    # ==================================================
    # GET JOB BY ID
    # ==================================================

    def get_job_by_id(
        self,
        db,
        job_id
    ):

        return (

            db.query(PublishJob)

            .filter(
                PublishJob.id == job_id
            )

            .first()
        )

    # ==================================================
    # GET PENDING JOBS
    # ==================================================

    def get_pending_jobs(
        self,
        db
    ):

        return (

            db.query(PublishJob)

            .filter(
                PublishJob.status == "pending"
            )

            .all()
        )

    # ==================================================
    # UPDATE JOB STATUS
    # ==================================================

    def update_job_status(
        self,
        db,
        job_id,
        status,
        error_message=None
    ):

        job = (

            db.query(PublishJob)

            .filter(
                PublishJob.id == job_id
            )

            .first()
        )

        if not job:

            return None

        job.status = status

        # ----------------------------------------------
        # OPTIONAL ERROR MESSAGE
        # ----------------------------------------------

        if (
            hasattr(
                job,
                "error_message"
            )
            and error_message
        ):

            job.error_message = (
                error_message
            )

        db.commit()

        db.refresh(job)

        return job

    # ==================================================
    # GET USER JOBS
    # ==================================================

    def get_user_jobs(
        self,
        db,
        user_id
    ):

        return (

            db.query(PublishJob)

            .filter(
                PublishJob.user_id == user_id
            )

            .all()
        )


publish_job_repository = (
    PublishJobRepository()
)