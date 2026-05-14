from celery import Celery

from app.core.config import settings


celery_app = Celery(

    "creator_ai_agent",

    broker=settings.REDIS_URL,

    backend=settings.REDIS_URL
)


# ======================================================
# CELERY CONFIG
# ======================================================

celery_app.conf.update(

    task_serializer="json",

    accept_content=["json"],

    result_serializer="json",

    timezone="Asia/Kolkata",

    enable_utc=False,

    task_track_started=True,

    task_time_limit=300,

    worker_prefetch_multiplier=1
)


# ======================================================
# AUTO DISCOVER TASKS
# ======================================================

celery_app.autodiscover_tasks(

    [

        "app.workers"
    ]
)