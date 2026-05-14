from celery import Celery
from app.core.config import settings

celery = Celery(
    "creator_agent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)