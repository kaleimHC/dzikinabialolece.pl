"""
Celery Tasks for Analytics app.

Queues: q_r (R spatial), q_cpu (Python ML), q_io (I/O)
"""

import os
from celery import shared_task
from django.core.cache import cache
from django.db import connection
import logging


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



@shared_task(
    bind=True,
    queue="q_cpu",  # Runs on worker-py with docker socket access
    soft_time_limit=1800,  # 30 min total
    time_limit=2100,  # 35 min hard limit
)
def run_r_pipeline_dev(self):
    # DISABLED 2026-01-18: under rewrite per spatialWarsaw methodology
    from django.core.cache import cache

    cache.set(
        "r_pipeline_progress",
        {
            "running": False,
            "current_step": 0,
            "total_steps": 5,
            "current_script": "",
            "error": "PUB pipeline wyłączony - w trakcie przepisywania według metodologii Kopczewskiej. Użyj trybu FAST.",
            "completed": False,
            "disabled": True,
        },
        timeout=3600,
    )
    cache.delete("recalculate_lock")
    return {
        "status": "disabled",
        "message": "PUB pipeline wyłączony - w trakcie przepisywania według metodologii Kopczewskiej. Użyj trybu FAST.",
        "redirect": "fast",
        "disabled_at": "2026-01-18",
        "reason": "Rewrite in progress",
    }



@shared_task(bind=True, queue="q_cpu", soft_time_limit=120, time_limit=180)
def recalculate_risk_model(self):
    """FAST mode recalculation — square grid only, never touches voronoi table."""
    logger.info("Starting FAST risk model recalculation (sightings_gridcell_square)")

    try:
        with connection.cursor() as cursor:
            cache.set(
                "r_pipeline_progress",
                {
                    "running": True,
                    "current_step": 1,
                    "total_steps": 4,
                    "current_script": "Zliczanie obserwacji (SQUARE)",
                    "error": None,
                    "completed": False,
                },
                timeout=3600,
            )

            cursor.execute("UPDATE sightings_gridcell_square SET sighting_count = 0;")
            cursor.execute("""
                UPDATE sightings_gridcell_square g SET sighting_count = subq.cnt
                FROM (
                    SELECT gc.grid_id, COUNT(s.id) as cnt
                    FROM sightings_gridcell_square gc
                    JOIN sightings_sighting s ON ST_Contains(gc.geometry, s.location)
                    WHERE s.status = 'verified'
                    GROUP BY gc.grid_id
                ) subq
                WHERE g.grid_id = subq.grid_id;
            """)
            new_assigned = cursor.rowcount

            cache.set(
                "r_pipeline_progress",
                {
                    "running": True,
                    "current_step": 2,
                    "total_steps": 4,
                    "current_script": "Obliczanie gestosci",
                    "error": None,
                    "completed": False,
                },
                timeout=3600,
            )

            cache.set(
                "r_pipeline_progress",
                {
                    "running": True,
                    "current_step": 3,
                    "total_steps": 4,
                    "current_script": "Obliczanie ryzyka",
                    "error": None,
                    "completed": False,
                },
                timeout=3600,
            )

            # Fixed thresholds based on data distribution (replaces PERCENT_RANK)
            cursor.execute(
                "UPDATE sightings_gridcell_square SET sighting_density = sighting_count / NULLIF(ST_Area(ST_Transform(geometry, 2180)) / 1000000.0, 0);"
            )
            cursor.execute("""
                UPDATE sightings_gridcell_square
                SET ensemble_risk = CASE 
                        WHEN sighting_count = 0 THEN 0.05
                        WHEN sighting_count = 1 THEN 0.40
                        WHEN sighting_count = 2 THEN 0.75
                        ELSE 0.95
                    END,
                    area_rank_score = CASE
                        WHEN sighting_count = 0 THEN 0.03
                        WHEN sighting_count = 1 THEN 0.25
                        WHEN sighting_count = 2 THEN 0.50
                        ELSE 0.70
                    END,
                    gwr_score = CASE
                        WHEN sighting_count = 0 THEN 0.02
                        WHEN sighting_count = 1 THEN 0.20
                        WHEN sighting_count = 2 THEN 0.45
                        ELSE 0.65
                    END;
            """)
            cursor.execute(
                "UPDATE sightings_gridcell_square SET confidence = CASE WHEN sighting_count = 0 THEN 0.2 WHEN sighting_count < 3 THEN 0.4 WHEN sighting_count < 6 THEN 0.6 ELSE 0.8 END;"
            )

            # Spatial smoothing - row-standardized weights
            cache.set(
                "r_pipeline_progress",
                {
                    "running": True,
                    "current_step": 4,
                    "total_steps": 4,
                    "current_script": "Smoothing row-standardized (W)",
                    "error": None,
                    "completed": False,
                },
                timeout=3600,
            )

            cursor.execute("""
                WITH hot_cells AS (
                    SELECT grid_id, geometry, ensemble_risk
                    FROM sightings_gridcell_square
                    WHERE sighting_count > 0
                ),
                neighbor_stats AS (
                    SELECT
                        g.grid_id,
                        g.ensemble_risk as own_risk,
                        COUNT(h.grid_id) as n_neighbors,
                        AVG(h.ensemble_risk) as avg_neighbor_risk
                    FROM sightings_gridcell_square g
                    JOIN hot_cells h ON g.geometry && ST_Expand(h.geometry, 0.002)
                        AND ST_DWithin(g.geometry::geography, h.geometry::geography, 150)
                        AND g.grid_id != h.grid_id
                        AND g.sighting_count = 0
                    GROUP BY g.grid_id, g.ensemble_risk
                )
                UPDATE sightings_gridcell_square g
                SET ensemble_risk = GREATEST(
                    g.ensemble_risk,
                    0.5 * ns.own_risk + 0.5 * ns.avg_neighbor_risk
                )
                FROM neighbor_stats ns
                WHERE g.grid_id = ns.grid_id AND ns.n_neighbors > 0;
            """)

            cursor.execute("UPDATE sightings_gridcell_square SET updated_at = NOW();")

            cursor.execute(
                "SELECT COUNT(*) FILTER (WHERE ensemble_risk >= 0.7) FROM sightings_gridcell_square;"
            )
            critical = cursor.fetchone()[0]
            cache.delete("sighting_stats")

        cache.set(
            "r_pipeline_progress",
            {
                "running": False,
                "current_step": 4,
                "total_steps": 4,
                "current_script": "Zakonczone",
                "error": None,
                "completed": True,
            },
            timeout=3600,
        )
        cache.delete("recalculate_lock")

        logger.info(f"Fast recalc (SQUARE): {new_assigned} new, {critical} critical")
        return {
            "status": "success",
            "new_sightings": new_assigned,
            "critical_cells": critical,
        }

    except Exception as exc:
        cache.set(
            "r_pipeline_progress",
            {
                "running": False,
                "current_step": 0,
                "total_steps": 4,
                "current_script": "",
                "error": str(exc),
                "completed": False,
            },
            timeout=3600,
        )
        cache.delete("recalculate_lock")
        raise



SAMPLE_FILES = {
    "mala": "baza_mala.json",
    "srednia": "baza_srednia.json",
    "duza": "baza_duza.json",
    "pelna": "baza_ogromna.json",
}


@shared_task(bind=True, queue="q_io", soft_time_limit=120, time_limit=180)
def switch_sample_task(self, sample: str):
    from django.core.management import call_command

    if sample not in SAMPLE_FILES:
        raise ValueError(f"Invalid sample: {sample}")

    fixture_file = f"/fixtures/samples/{SAMPLE_FILES[sample]}"
    total_steps = 4

    def update_progress(step, message):
        cache.set(
            "sample_switch_progress",
            {
                "running": True,
                "task_id": self.request.id,
                "sample": sample,
                "current": step,
                "total": total_steps,
                "step": message,
                "message": message,
                "error": None,
            },
            timeout=600,
        )

    try:
        update_progress(1, "Czyszczenie danych...")
        logger.info(f"Switching to sample: {sample}")

        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE sightings_sighting CASCADE;")

        update_progress(2, "Ładowanie próby...")
        call_command("loaddata", fixture_file, verbosity=0)

        update_progress(3, "Przeliczanie siatki...")

        with connection.cursor() as cursor:
            cursor.execute("UPDATE sightings_gridcell SET sighting_count = 0;")

            # Count sightings per grid cell using spatial join (no grid_cell_id assignment)
            cursor.execute("""
                UPDATE sightings_gridcell g SET sighting_count = COALESCE(subq.cnt, 0)
                FROM (
                    SELECT gc.grid_id, COUNT(s.id) as cnt
                    FROM sightings_gridcell gc
                    LEFT JOIN sightings_sighting s ON ST_Contains(gc.geometry, s.location)
                    WHERE s.status = 'verified' OR s.id IS NULL
                    GROUP BY gc.grid_id
                ) subq
                WHERE g.grid_id = subq.grid_id;
            """)

            # EPSG:2180 for area avoids latitude bias in density calculation
            cursor.execute("""
                UPDATE sightings_gridcell
                SET sighting_density = sighting_count / NULLIF(ST_Area(ST_Transform(geometry, 2180)) / 1000000.0, 0);
            """)

            # Fixed thresholds based on data distribution (replaces PERCENT_RANK)
            cursor.execute("""
                UPDATE sightings_gridcell
                SET ensemble_risk = CASE
                        WHEN sighting_count = 0 THEN 0.05
                        WHEN sighting_count = 1 THEN 0.40
                        WHEN sighting_count = 2 THEN 0.75
                        ELSE 0.95
                    END,
                    area_rank_score = CASE
                        WHEN sighting_count = 0 THEN 0.03
                        WHEN sighting_count = 1 THEN 0.25
                        WHEN sighting_count = 2 THEN 0.50
                        ELSE 0.70
                    END,
                    gwr_score = CASE
                        WHEN sighting_count = 0 THEN 0.02
                        WHEN sighting_count = 1 THEN 0.20
                        WHEN sighting_count = 2 THEN 0.45
                        ELSE 0.65
                    END;
            """)

        update_progress(4, "Weryfikacja...")

        from sightings.models import Sighting

        final_count = Sighting.objects.count()

        cache.delete("sighting_stats")

        cache.set(
            "sample_switch_progress",
            {
                "running": False,
                "task_id": self.request.id,
                "sample": sample,
                "current": total_steps,
                "total": total_steps,
                "step": "completed",
                "message": f"Załadowano {final_count} obserwacji",
                "error": None,
            },
            timeout=600,
        )

        logger.info(f"Sample switch complete: {sample} ({final_count} sightings)")
        return {"status": "success", "sample": sample, "sighting_count": final_count}

    except Exception as exc:
        error_msg = str(exc)
        logger.exception(f"Sample switch error: {error_msg}")

        cache.set(
            "sample_switch_progress",
            {
                "running": False,
                "task_id": self.request.id,
                "sample": sample,
                "current": 0,
                "total": total_steps,
                "step": "error",
                "message": "Błąd",
                "error": error_msg,
            },
            timeout=600,
        )

        raise


from analytics.tasks_research import run_research_pipeline  # noqa: F401, E402
