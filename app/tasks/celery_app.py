from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "local_scout_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_time_limit=1800,
    task_soft_time_limit=1500,
)

celery_app.conf.beat_schedule = {
    "area-crawl-refresh": {
        "task": "app.tasks.crawl_tasks.scheduled_area_refresh",
        "schedule": crontab(minute=0, hour="*/12"),
        "options": {"expires": 3600},
    },
    "knowledge-crawler-update": {
        "task": "app.tasks.knowledge_tasks.run_knowledge_crawler",
        "schedule": crontab(minute=0, hour=2, day_of_week=1),
        "options": {"expires": 7200},
    },
    "model-improvement-check": {
        "task": "app.tasks.knowledge_tasks.check_model_improvements",
        "schedule": crontab(minute=30, hour=2, day_of_week=1),
        "options": {"expires": 7200},
    },
}

celery_app.autodiscover_tasks(["app.tasks"])
