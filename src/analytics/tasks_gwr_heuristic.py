"""
GWR Heuristic - Environmental proxy for GWR when real GWR unavailable.
DEBUG-FIRST: Every step logged!

Formula:
  GWR_score = 0.40*forest_cover + 0.30*water_proximity + 0.30*(1-building_density)

Where:
  - forest_cover: 0-1 (higher = more habitat)
  - water_proximity: 1 - (distance_to_water / 2000), clamped 0-1
  - building_density: 0-1 (higher = less suitable)
"""

import uuid
import logging
from celery import shared_task
from django.db import connection
from analytics.sql_injection_patch import validate_grid_type

from analytics.debug_mode import DebugLogger

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="analytics.tasks_gwr_heuristic.compute_gwr_heuristic",
    queue="q_cpu",
    soft_time_limit=120,
    time_limit=180,
)
def compute_gwr_heuristic(self, grid_type: str = "voronoi", run_id: str = None):
    """
    Compute GWR heuristic (environmental proxy).
    DEBUG-FIRST: Every step logged!
    """
    run_id = run_id or str(uuid.uuid4())[:12]
    debug = DebugLogger(run_id, mode="FAST", module="GWR_HEURISTIC")

    grid_table = validate_grid_type(grid_type)

    try:
        # Step 1: Load current data
        t = debug.start("load_data", f"Loading {grid_type} cells")

        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT COUNT(*),
                       AVG(forest_cover), MIN(forest_cover), MAX(forest_cover),
                       AVG(distance_to_water), MIN(distance_to_water), MAX(distance_to_water),
                       AVG(building_density), MIN(building_density), MAX(building_density),
                       AVG(gwr_score)
                FROM {grid_table}
            """)
            stats = cursor.fetchone()

        debug.success(
            "load_data",
            f"Loaded {stats[0]} cells",
            values={
                "count": stats[0],
                "forest_cover": {
                    "avg": round(stats[1] or 0, 4),
                    "min": round(stats[2] or 0, 4),
                    "max": round(stats[3] or 0, 4),
                },
                "distance_to_water": {
                    "avg": round(stats[4] or 0, 2),
                    "min": round(stats[5] or 0, 2),
                    "max": round(stats[6] or 0, 2),
                },
                "building_density": {
                    "avg": round(stats[7] or 0, 4),
                    "min": round(stats[8] or 0, 4),
                    "max": round(stats[9] or 0, 4),
                },
                "current_gwr_avg": round(stats[10] or 0, 4),
            },
            start_time=t,
        )

        # Step 2: Compute heuristic
        t = debug.start("compute_heuristic", "Computing GWR heuristic formula")

        # Formula: 0.40*forest + 0.30*water_prox + 0.30*(1-building)
        # water_prox = GREATEST(0, 1 - distance_to_water/2000)
        with connection.cursor() as cursor:
            cursor.execute(f"""
                UPDATE {grid_table}
                SET gwr_score = ROUND((
                    0.40 * COALESCE(forest_cover, 0) +
                    0.30 * GREATEST(0, LEAST(1, 1 - COALESCE(distance_to_water, 1000) / 2000.0)) +
                    0.30 * (1 - COALESCE(building_density, 0))
                )::numeric, 6)
            """)
            updated = cursor.rowcount

        debug.success(
            "compute_heuristic",
            f"Updated {updated} cells",
            values={
                "updated": updated,
                "formula": "0.40*forest + 0.30*water_prox + 0.30*(1-building)",
                "water_prox_formula": "max(0, 1 - distance/2000)",
            },
            start_time=t,
        )

        # Step 3: Verify results
        t = debug.start("verify", "Verifying GWR heuristic values")

        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    COUNT(*),
                    COUNT(DISTINCT ROUND(gwr_score::numeric, 4)),
                    MIN(gwr_score), MAX(gwr_score), AVG(gwr_score), STDDEV(gwr_score),
                    COUNT(*) FILTER (WHERE gwr_score = 0.5),
                    COUNT(*) FILTER (WHERE gwr_score < 0.3),
                    COUNT(*) FILTER (WHERE gwr_score > 0.7)
                FROM {grid_table}
                WHERE gwr_score IS NOT NULL
            """)
            verify = cursor.fetchone()

        verification = {
            "total": verify[0],
            "unique_values": verify[1],
            "gwr_min": round(float(verify[2]), 4) if verify[2] else None,
            "gwr_max": round(float(verify[3]), 4) if verify[3] else None,
            "gwr_mean": round(float(verify[4]), 4) if verify[4] else None,
            "gwr_std": round(float(verify[5]), 4) if verify[5] else None,
            "still_placeholder_0.5": verify[6],
            "low_risk_below_0.3": verify[7],
            "high_risk_above_0.7": verify[8],
        }

        if (
            verification["unique_values"] > 10
            and verification["still_placeholder_0.5"] == 0
        ):
            debug.success(
                "verify",
                "GWR heuristic verification PASSED",
                values=verification,
                start_time=t,
            )
        elif verification["still_placeholder_0.5"] > 0:
            debug.warning(
                "verify",
                f"Still {verification['still_placeholder_0.5']} cells with placeholder 0.5",
                values=verification,
            )
        else:
            debug.warning(
                "verify",
                f"Low variance: only {verification['unique_values']} unique values",
                values=verification,
            )

        # Step 4: Recalculate ensemble
        t = debug.start("recalc_ensemble", "Recalculating ensemble risk")

        with connection.cursor() as cursor:
            cursor.execute(f"""
                UPDATE {grid_table}
                SET ensemble_risk = ROUND((
                    0.30 * COALESCE(rf_score, 0.5) +
                    0.40 * COALESCE(gwr_score, 0.5) +
                    0.30 * COALESCE(area_rank_score, 0.5)
                )::numeric, 6),
                updated_at = NOW()
            """)
            ensemble_updated = cursor.rowcount

        # Get ensemble stats
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT MIN(ensemble_risk), MAX(ensemble_risk), AVG(ensemble_risk),
                       COUNT(DISTINCT ROUND(ensemble_risk::numeric, 4))
                FROM {grid_table}
            """)
            ens_stats = cursor.fetchone()

        debug.success(
            "recalc_ensemble",
            f"Updated {ensemble_updated} ensemble values",
            values={
                "updated": ensemble_updated,
                "formula": "0.30*RF + 0.40*GWR + 0.30*ETA",
                "ensemble_min": round(float(ens_stats[0]), 4) if ens_stats[0] else None,
                "ensemble_max": round(float(ens_stats[1]), 4) if ens_stats[1] else None,
                "ensemble_mean": round(float(ens_stats[2]), 4)
                if ens_stats[2]
                else None,
                "ensemble_unique": ens_stats[3],
            },
            start_time=t,
        )

        summary = debug.summary()

        return {
            "status": "success",
            "grid_type": grid_type,
            "run_id": run_id,
            "cells_updated": updated,
            **verification,
            "ensemble_min": round(float(ens_stats[0]), 4) if ens_stats[0] else None,
            "ensemble_max": round(float(ens_stats[1]), 4) if ens_stats[1] else None,
            "ensemble_mean": round(float(ens_stats[2]), 4) if ens_stats[2] else None,
            "_debug_summary": summary,
        }

    except Exception as exc:
        debug.error("task_failed", f"GWR heuristic error: {str(exc)}")
        debug.summary()
        logger.exception(f"GWR heuristic error: {exc}")
        raise
