from sqlalchemy.orm import Session

from app.models.publish_job import (
    PublishJob
)


class PublishJobRepository:

    def create_job(
        self,
        db: Session,
        user_id: int,
        post_id: int,
        platform: str,
        scheduled_time = None
    ):

        job = PublishJob(

            user_id=user_id,

            post_id=post_id,

            platform=platform,

            scheduled_time=
            scheduled_time
        )

        db.add(job)

        db.commit()

        db.refresh(job)

        return job

    def get_pending_jobs(
        self,
        db: Session
    ):

        return (

            db.query(PublishJob)

            .filter(
                PublishJob.status
                == "pending"
            )

            .all()
        )

    def update_job_status(
        self,
        db: Session,
        job_id: int,
        status: str,
        error_message: str = None
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

        if error_message:

            job.error_message = (
                error_message
            )

        db.commit()

        db.refresh(job)

        return job


publish_job_repository = (
    PublishJobRepository()
)