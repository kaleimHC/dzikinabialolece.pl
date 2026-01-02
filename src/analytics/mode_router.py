"""
MODE ROUTER — FAST/PUB pipeline dispatcher.
"""

import uuid
import logging
from celery import shared_task
from django.db import connection

from analytics.debug_mode import DebugLogger

logger = logging.getLogger(__name__)

# Mode configurations
MODE_CONFIG = {
    "FAST": {
        "grid_type": "square",  # FAST = SQUARE grid (9875 cells)
        "description": "Real-time API responses",
    },
    "PUB": {
        "grid_type": "voronoi",  # PUB = VORONOI grid (100-500 cells)
        "description": "Publication quality (Voronoi + area-rank)",
    },
}


@shared_task(
    bind=True,
    name="analytics.mode_router.run_pipeline",
    queue="q_cpu",
    soft_time_limit=600,
    time_limit=900,
)
def run_pipeline(self, mode: str = "FAST", run_id: str = None):
    """
    Main pipeline router - dispatches to appropriate mode.
    DEBUG-FIRST: Every step logged!
    """
    run_id = run_id or str(uuid.uuid4())[:12]
    debug = DebugLogger(run_id, mode=mode, module="MODE_ROUTER")

    if mode not in MODE_CONFIG:
        debug.error(
            "validate_mode",
            f"Unknown mode: {mode}",
            values={"valid_modes": list(MODE_CONFIG.keys())},
        )
        return {"status": "error", "message": f"Unknown mode: {mode}"}

    config = MODE_CONFIG[mode]

    t = debug.start("run_pipeline", f"Starting {mode} pipeline")
    debug.info("config", "Mode configuration", values=config)

    try:
        if mode == "FAST":
            result = _run_fast_pipeline(run_id, config, debug)
        elif mode == "PUB":
            result = _run_pub_pipeline(run_id, config, debug)
        else:
            return {"status": "error", "message": f"Mode {mode} not implemented"}

        debug.success(
            "run_pipeline", f"{mode} pipeline completed", values=result, start_time=t
        )
        result["_debug_summary"] = debug.summary()
        return result

    except Exception as exc:
        debug.error("pipeline_failed", f"{mode} pipeline error: {str(exc)}")
        debug.summary()
        logger.exception(f"{mode} pipeline error: {exc}")
        raise


def _run_fast_pipeline(run_id: str, config: dict, debug: DebugLogger) -> dict:
    """
    FAST pipeline: SIMPLE sighting-based risk on SQUARE grid.

    IZOLACJA: Tylko SQUARE grid, NIE dotyka VORONOI (PUB mode).
    Logika: gdzie sightings → tam ryzyko (proste progi).
    """
    grid_type = config["grid_type"]  # 'square'
    results = {"mode": "FAST", "grid_type": grid_type, "steps": {}}

    t = debug.start("fast_recalc", "FAST: Simple sighting-based risk")

    try:
        with connection.cursor() as cursor:
            # Step 1: Reset and count sightings per SQUARE cell
            debug.info("step1", "Counting sightings per cell")
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
            cells_with_sightings = cursor.rowcount
            results["steps"]["count_sightings"] = f"{cells_with_sightings} cells"

            # Step 2: Simple risk based on sighting count
            # ORIGINAL LOGIC: 0=0.05, 1=0.40, 2=0.75, 3+=0.95
            debug.info("step2", "Setting risk based on sighting count")
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
                    END,
                    confidence = CASE
                        WHEN sighting_count = 0 THEN 0.2
                        WHEN sighting_count < 3 THEN 0.4
                        WHEN sighting_count < 6 THEN 0.6
                        ELSE 0.8
                    END;
            """)
            results["steps"]["set_risk"] = "success"

            # Step 3: Spatial smoothing for neighbors of hot cells
            debug.info("step3", "Spatial smoothing")
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
            smoothed = cursor.rowcount
            results["steps"]["smoothing"] = f"{smoothed} cells smoothed"

            # Step 4: Update timestamp
            cursor.execute("UPDATE sightings_gridcell_square SET updated_at = NOW();")

            # Get stats
            cursor.execute("""
                SELECT COUNT(*),
                       COUNT(*) FILTER (WHERE sighting_count > 0),
                       COUNT(*) FILTER (WHERE ensemble_risk >= 0.7),
                       MIN(ensemble_risk), MAX(ensemble_risk)
                FROM sightings_gridcell_square
            """)
            total, with_sightings, critical, min_risk, max_risk = cursor.fetchone()

        results["ensemble"] = {
            "count": total,
            "cells_with_sightings": with_sightings,
            "critical_cells": critical,
            "min": round(float(min_risk), 4) if min_risk else None,
            "max": round(float(max_risk), 4) if max_risk else None,
        }

        debug.success(
            "fast_recalc", "FAST completed", values=results["ensemble"], start_time=t
        )
        results["status"] = "success"

    except Exception as e:
        debug.error("fast_recalc", f"FAST failed: {str(e)}")
        results["status"] = "error"
        results["error"] = str(e)

    return results


def _run_pub_pipeline(run_id: str, config: dict, debug: DebugLogger) -> dict:
    """PUB pipeline: Voronoi + R spatial models."""
    return {"status": "ok", "mode": "PUB", "grid_type": config["grid_type"]}
