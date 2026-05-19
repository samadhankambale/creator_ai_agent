from datetime import datetime
from sqlalchemy.orm import Session
from app.models.publish_job import PublishJob


class PublishJobRepository:

    def create(
        self,
        db: Session,
        user_id: int,
        post_id: int,
        platform: str,
        scheduled_time=None,
    ) -> PublishJob:
        job = PublishJob(
            user_id=user_id,
            post_id=post_id,
            platform=platform,
            scheduled_time=scheduled_time,
            status="pending",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    # alias — old code used this name
    def create_job(self, db, user_id, post_id, platform, scheduled_time=None):
        return self.create(db, user_id, post_id, platform, scheduled_time)

    def get_by_id(self, db: Session, job_id: int):
        return (
            db.query(PublishJob)
            .filter(PublishJob.id == job_id)
            .first()
        )

    # alias — old code used this name
    def get_job_by_id(self, db: Session, job_id: int):
        return self.get_by_id(db, job_id)

    def get_pending_due(self, db: Session):
        """Scheduled jobs whose time has arrived."""
        now = datetime.utcnow()
        return (
            db.query(PublishJob)
            .filter(
                PublishJob.status == "pending",
                PublishJob.scheduled_time <= now,
                PublishJob.scheduled_time != None,
            )
            .all()
        )

    def get_pending_jobs(self, db: Session):
        """All pending jobs (old method name)."""
        return (
            db.query(PublishJob)
            .filter(PublishJob.status == "pending")
            .all()
        )

    def mark_done(self, db: Session, job_id: int):
        job = self.get_by_id(db, job_id)
        if job:
            job.status = "done"
            job.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(job)
        return job

    def mark_failed(self, db: Session, job_id: int, error: str):
        job = self.get_by_id(db, job_id)
        if job:
            job.status = "failed"
            job.error_message = error
            job.retry_count = (job.retry_count or 0) + 1
            db.commit()
            db.refresh(job)
        return job

    # alias — old code used this name
    def update_job_status(self, db, job_id, status, error_message=None):
        if status == "done":
            return self.mark_done(db, job_id)
        return self.mark_failed(db, job_id, error_message or "")

    def get_user_jobs(self, db: Session, user_id: int):
        return (
            db.query(PublishJob)
            .filter(PublishJob.user_id == user_id)
            .all()
        )


publish_job_repository = PublishJobRepository()