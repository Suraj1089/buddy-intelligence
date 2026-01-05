"""
Celery application configuration for background tasks.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "buddy_tasks",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=["app.tasks.assignment_tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    worker_prefetch_multiplier=1,
    result_expires=3600,  # 1 hour
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "check-expired-assignments": {
        "task": "app.tasks.assignment_tasks.check_expired_assignments",
        "schedule": 60.0,  # Every minute
    },
    "process-unassigned-bookings": {
        "task": "app.tasks.assignment_tasks.process_unassigned_bookings",
        "schedule": 60.0,  # Every minute
    },
    "notify-awaiting-bookings": {
        "task": "app.tasks.assignment_tasks.notify_awaiting_bookings",
        "schedule": 60.0,  # Every minute
    },
    "assign-upcoming-bookings": {
        "task": "app.tasks.assignment_tasks.assign_upcoming_bookings",
        "schedule": 3600.0,  # Every hour - picks up scheduled bookings 24h before service
    },
}
