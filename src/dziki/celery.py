"""
Celery configuration for Dziki na Białołęce project.

Task routing (worker-py consumes q_cpu + q_io):
- q_cpu: Python ensemble and R-spatial tasks -> worker-py
- q_io: I/O (MV refresh, cache warmup) -> worker-py
- q_r: reserved for a dedicated R worker, currently unused
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dziki.settings")

# Create Celery app
app = Celery("dziki")

# Load config from Django settings (CELERY_ prefix)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all registered Django apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery connectivity."""
    print(f"Request: {self.request!r}")


# CELERY BEAT SCHEDULE
# DR-10 CRITICAL: Each scheduled task MUST have 'options': {'queue': 'name'}
# Without 'options', tasks go to default 'celery' queue, ignoring TASK_ROUTES!

app.conf.beat_schedule = {
    # -------------------------------------------------------------------------
    # I/O TASKS (queue: q_io)
    # -------------------------------------------------------------------------
    # Daily materialized view refresh (every day at 4:00 AM)
    "refresh-mv-daily": {
        "task": "analytics.tasks.refresh_materialized_views",
        "schedule": crontab(hour=4, minute=0),
        "options": {
            "queue": "q_io",
            "time_limit": 600,
            "soft_time_limit": 540,
        },
    },
    # Hourly cache warmup (every hour at :05)
    "warmup-cache-hourly": {
        "task": "analytics.tasks.warmup_cache",
        "schedule": crontab(minute=5),
        "options": {
            "queue": "q_io",
            "time_limit": 300,
            "soft_time_limit": 270,
        },
    },
}

# WORKER CONFIGURATION NOTES
# DR-8 CRITICAL: Use --max-tasks-per-child=50 (not 1) for R workers
# --max-tasks-per-child=1 has HIGH overhead (~500ms-1s per restart)
# --max-tasks-per-child=50 balances memory safety and performance
#
# worker-r (rocker/geospatial) - for R tasks:
#   celery -A dziki worker -Q q_r \
#     --pool=prefork \
#     --concurrency=2 \
#     --max-tasks-per-child=50 \
#     -E
#   Environment: OMP_NUM_THREADS=1
#
# worker-py (python:3.11-slim) - for Python ML tasks:
#   celery -A dziki worker -Q q_cpu,q_io \
#     --pool=prefork \
#     --concurrency=4 \
#     --max-tasks-per-child=100
#
# beat (scheduler):
#   celery -A dziki beat --scheduler django_celery_beat.schedulers:DatabaseScheduler
#
#
