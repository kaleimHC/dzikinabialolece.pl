"""
Celery configuration for Dziki na Białołęce project.
MASTER_SPEC v2.2 Architecture

VERIFIED AGAINST:
- DR-8: prefork pool, max-tasks-per-child=50 (not 1)
- DR-9: soft_time_limit before time_limit
- DR-10: beat_schedule MUST have 'options': {'queue': 'name'}
- NotebookLM Q11-Q15: All settings validated

Task routing:
- q_r: R Spatial (GWR, ETA, STS) -> worker-r (rocker/geospatial)
- q_bayes: Bayesian SSM, Trajectories -> worker-bayes (MASTER_SPEC I.3)
- q_cpu: Python ML (RF, Ensemble) -> worker-py
- q_io: I/O (MV refresh, tiles) -> worker-io
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
    # R SPATIAL TASKS (queue: q_r)
    # -------------------------------------------------------------------------
    # Weekly GWR computation (Sunday 3:00 AM)
    # NotebookLM Q14: Weekly schedule confirmed
    "compute-gwr-weekly": {
        "task": "analytics.tasks.compute_gwr_weekly",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday
        "options": {
            "queue": "q_r",
            "time_limit": 7200,  # 120 min hard limit
            "soft_time_limit": 7080,  # 118 min soft limit (DR-9)
        },
    },
    # Daily ETA computation (every day at 2:00 AM)
    # NotebookLM Q14: Daily schedule confirmed
    "compute-eta-daily": {
        "task": "analytics.tasks.compute_eta",
        "schedule": crontab(hour=2, minute=0),
        "options": {
            "queue": "q_r",
            "time_limit": 7200,
            "soft_time_limit": 7080,
        },
    },
    # Monthly STS computation (1st day of month at 5:00 AM)
    # NotebookLM Q14, Q15: Monthly schedule, 240 min timeout
    "compute-sts-monthly": {
        "task": "analytics.tasks.compute_sts",
        "schedule": crontab(hour=5, minute=0, day_of_month=1),
        "options": {
            "queue": "q_r",
            "time_limit": 14400,  # 240 min hard limit (STS specific)
            "soft_time_limit": 14280,  # 238 min soft limit
        },
    },
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
#   celery -A dziki worker -Q q_cpu \
#     --pool=prefork \
#     --concurrency=4 \
#     --max-tasks-per-child=100
#
# worker-io - for I/O tasks:
#   celery -A dziki worker -Q q_io \
#     --pool=prefork \
#     --concurrency=8
#
# beat (scheduler):
#   celery -A dziki beat --scheduler django_celery_beat.schedulers:DatabaseScheduler
#
# worker-bayes (Dockerfile.rstan-spatial) - for Bayesian tasks:
#   celery -A dziki worker -Q q_bayes \
#     --pool=prefork \
#     --concurrency=1 \
#     --max-tasks-per-child=1
#   Environment: R_MAX_VSIZE=8Gb
#   Memory limit: 8GB (MCMC is memory-intensive)
#   Note: Only started when bayes-tasks profile is enabled
#
