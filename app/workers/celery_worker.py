from celery import Celery

from app.core.config import settings


from celery import Celery

from app.core.config import settings


celery_app = Celery(

    "creator_agent",

    broker=settings.REDIS_URL,

    backend=settings.REDIS_URL,

    include=[
        "app.workers.scheduled_post_worker"
    ]
)


celery_app.conf.update(

    task_serializer="json",

    accept_content=["json"],

    result_serializer="json",

    timezone="Asia/Kolkata",

    enable_utc=True
)