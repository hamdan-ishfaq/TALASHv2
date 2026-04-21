import os

from celery import Celery

celery_app = Celery(
    "talash",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
    include=["worker.cv_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Duplicate prevention & resilience
    task_acks_late=True,           # Ack only after successful completion (prevents resend on crash)
    task_reject_on_worker_lost=True,  # Reject if worker dies without acknowledgement
    task_max_retries=2,            # Max 2 retries on transient failures
    task_time_limit=3600,          # Hard limit: 1 hour per task
    task_soft_time_limit=3300,     # Soft limit: 55 min (allows graceful shutdown)
)
