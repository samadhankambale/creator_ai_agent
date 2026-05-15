from celery.schedules import crontab

from app.workers.celery_worker import (
    celery_app
)


celery_app.conf.beat_schedule = {

    "process-scheduled-jobs": {

        "task": (
            "app.workers.scheduled_post_worker"
            ".process_scheduled_jobs"
        ),

        "schedule": 60.0
    }
}