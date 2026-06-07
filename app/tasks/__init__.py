from app.tasks.celery_app import celery_app
from app.tasks.crawl_tasks import (
    crawl_area_task,
    process_document_task,
    score_reviews_task,
    scheduled_area_refresh,
)
from app.tasks.knowledge_tasks import run_knowledge_crawler, check_model_improvements

__all__ = [
    "celery_app",
    "crawl_area_task",
    "process_document_task",
    "score_reviews_task",
    "scheduled_area_refresh",
    "run_knowledge_crawler",
    "check_model_improvements",
]
