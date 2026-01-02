"""
Celery Tasks for Analytics app.

Queues: q_r (R spatial), q_cpu (Python ML), q_io (I/O)
"""

import os
from celery import shared_task
from django.core.cache import cache
from django.db import connection
import logging

# mode_router defines run_pipeline as @shared_task but is not named tasks.py,
# so Celery autodiscover_tasks() misses it. Import here to register it.
from analytics.mode_router import run_pipeline as _run_pipeline_task  # noqa: F401

logger = logging.getLogger(__name__)



@shared_task(
    bind=True,
    queue="q_io",
    soft_time_limit=300,
    time_limit=600,
)
def refresh_materialized_views(self):
    """Refresh materialized views with CONCURRENTLY (no table lock)."""
    logger.info("Starting MV refresh")

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY IF EXISTS mv_sighting_stats;"
            )
            cursor.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY IF EXISTS mv_grid_stats;"
            )

        cache.delete("sighting_stats")
        cache.delete("grid_stats")

        logger.info("MV refresh completed")
        return {"status": "success"}

    except Exception as exc:
        logger.exception(f"MV refresh error: {exc}")
        raise


@shared_task(queue="q_io")
def warmup_cache():
    logger.info("Starting cache warmup")

    try:
        from sightings.models import Sighting
        from django.utils import timezone
        from datetime import timedelta

        queryset = Sighting.objects.filter(status=Sighting.Status.VERIFIED)
        week_ago = timezone.now() - timedelta(days=7)
        month_ago = timezone.now() - timedelta(days=30)

        stats = {
            "total": queryset.count(),
            "last_7_days": queryset.filter(observed_at__gte=week_ago).count(),
            "last_30_days": queryset.filter(observed_at__gte=month_ago).count(),
        }

        cache.set("sighting_stats", stats, timeout=3600)

        logger.info("Cache warmup completed")
        return {"status": "success", "stats": stats}

    except Exception as exc:
        logger.exception(f"Cache warmup error: {exc}")
        raise


@shared_task(bind=True, queue="q_cpu", soft_time_limit=120, time_limit=180)
def recalculate_risk_model(self):
    """FAST mode recalculation — square grid only, never touches voronoi table."""
    logger.info("Starting FAST risk model recalculation (sightings_gridcell_square)")
    return {"status": "stub"}
