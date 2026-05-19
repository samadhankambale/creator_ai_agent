from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "creator_agent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.scheduled_post_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    # Poll every 60 seconds for scheduled jobs
    beat_schedule={
        "run-scheduled-jobs": {
            "task": "app.workers.scheduled_post_worker.run_scheduled_jobs",
            "schedule": 60.0,
        }
    },
)