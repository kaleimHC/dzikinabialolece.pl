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


def _calculate_osm_features(debug: DebugLogger) -> dict:
    """
    Calculate OSM environmental features for Voronoi cells.
    MUST run after 01_generate_voronoi.R (which TRUNCATES the table).

    Calculates:
    - forest_cover: % of cell covered by forest
    - building_density: % of cell covered by buildings
    - road_density: km of roads per km² of cell
    - distance_to_water: distance from centroid to nearest water body
    """
    t = debug.start("osm_features", "Calculating OSM environmental features")

    results = {"step": "osm_features", "updated": {}}

    try:
        with connection.cursor() as cursor:
            # 1. Forest cover (% area)
            debug.info("forest", "Calculating forest_cover...")
            cursor.execute("""
                UPDATE sightings_gridcell_voronoi gc
                SET forest_cover = COALESCE(subq.cover, 0)
                FROM (
                    SELECT
                        gc2.id,
                        SUM(ST_Area(ST_Intersection(gc2.geometry, f.geom)::geography)) /
                            NULLIF(ST_Area(gc2.geometry::geography), 0) as cover
                    FROM sightings_gridcell_voronoi gc2
                    LEFT JOIN osm_forests f ON ST_Intersects(gc2.geometry, f.geom)
                    GROUP BY gc2.id
                ) subq
                WHERE gc.id = subq.id;
            """)
            results["updated"]["forest_cover"] = cursor.rowcount

            # 2. Building density (% area)
            debug.info("building", "Calculating building_density...")
            cursor.execute("""
                UPDATE sightings_gridcell_voronoi gc
                SET building_density = COALESCE(subq.density, 0)
                FROM (
                    SELECT
                        gc2.id,
                        SUM(ST_Area(ST_Intersection(gc2.geometry, b.geom)::geography)) /
                            NULLIF(ST_Area(gc2.geometry::geography), 0) as density
                    FROM sightings_gridcell_voronoi gc2
                    LEFT JOIN osm_buildings b ON ST_Intersects(gc2.geometry, b.geom)
                    GROUP BY gc2.id
                ) subq
                WHERE gc.id = subq.id;
            """)
            results["updated"]["building_density"] = cursor.rowcount

            # 3. Road density (km/km²)
            debug.info("road", "Calculating road_density...")
            cursor.execute("""
                UPDATE sightings_gridcell_voronoi gc
                SET road_density = COALESCE(subq.density, 0)
                FROM (
                    SELECT
                        gc2.id,
                        SUM(ST_Length(ST_Intersection(gc2.geometry, r.geom)::geography)) / 1000 /
                            NULLIF(ST_Area(gc2.geometry::geography) / 1000000, 0) as density
                    FROM sightings_gridcell_voronoi gc2
                    LEFT JOIN osm_roads r ON ST_Intersects(gc2.geometry, r.geom)
                    GROUP BY gc2.id
                ) subq
                WHERE gc.id = subq.id;
            """)
            results["updated"]["road_density"] = cursor.rowcount

            # 4. Distance to water (meters)
            debug.info("water", "Calculating distance_to_water...")
            cursor.execute("""
                UPDATE sightings_gridcell_voronoi gc
                SET distance_to_water = COALESCE(subq.dist, 9999)
                FROM (
                    SELECT
                        gc2.id,
                        MIN(ST_Distance(gc2.centroid::geography, w.geom::geography)) as dist
                    FROM sightings_gridcell_voronoi gc2
                    CROSS JOIN osm_water w
                    GROUP BY gc2.id
                ) subq
                WHERE gc.id = subq.id;
            """)
            results["updated"]["distance_to_water"] = cursor.rowcount

            # Get stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN forest_cover > 0 THEN 1 ELSE 0 END) as has_forest,
                    SUM(CASE WHEN building_density > 0 THEN 1 ELSE 0 END) as has_building,
                    SUM(CASE WHEN road_density > 0 THEN 1 ELSE 0 END) as has_road,
                    ROUND(AVG(forest_cover)::numeric, 4) as avg_forest,
                    ROUND(AVG(building_density)::numeric, 4) as avg_building,
                    ROUND(AVG(road_density)::numeric, 2) as avg_road
                FROM sightings_gridcell_voronoi
            """)
            stats = cursor.fetchone()
            results["stats"] = {
                "total_cells": stats[0],
                "cells_with_forest": stats[1],
                "cells_with_building": stats[2],
                "cells_with_road": stats[3],
                "avg_forest_cover": float(stats[4]) if stats[4] else 0,
                "avg_building_density": float(stats[5]) if stats[5] else 0,
                "avg_road_density": float(stats[6]) if stats[6] else 0,
            }

        results["status"] = "success"
        debug.success(
            "osm_features",
            "OSM features calculated",
            values=results["stats"],
            start_time=t,
        )

    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)
        debug.error("osm_features", f"OSM features failed: {str(e)}")

    return results


def _calculate_population(debug: DebugLogger) -> dict:
    """
    Calculate area-weighted population for Voronoi cells from GUS 500m grid.
    MUST run after 01_generate_voronoi.R (which TRUNCATES the table).

    Formula: population = SUM(gus.tot * overlap_area / gus_cell_area)
    This distributes GUS grid population proportionally to the overlap
    between each Voronoi cell and intersecting GUS cells.
    """
    t = debug.start(
        "population", "Calculating area-weighted population from GUS 500m grid"
    )

    results = {"step": "population"}

    try:
        with connection.cursor() as cursor:
            debug.info("population", "Running area-weighted join...")
            cursor.execute("""
                UPDATE sightings_gridcell_voronoi gc
                SET population = COALESCE(subq.pop, 0)
                FROM (
                    SELECT
                        v.id,
                        SUM(
                            g.tot *
                            ST_Area(ST_Intersection(v.geometry, g.geom)::geography) /
                            NULLIF(ST_Area(g.geom::geography), 0)
                        ) as pop
                    FROM sightings_gridcell_voronoi v
                    LEFT JOIN gus_population_grid_500m g
                        ON ST_Intersects(v.geometry, g.geom)
                    GROUP BY v.id
                ) subq
                WHERE gc.id = subq.id;
            """)
            updated = cursor.rowcount

            # Get stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE population > 0) as has_pop,
                    ROUND(MIN(population)::numeric, 1) as min_pop,
                    ROUND(MAX(population)::numeric, 1) as max_pop,
                    ROUND(AVG(population)::numeric, 1) as avg_pop,
                    ROUND(SUM(population)::numeric, 0) as total_pop
                FROM sightings_gridcell_voronoi
            """)
            stats = cursor.fetchone()
            results["stats"] = {
                "total_cells": stats[0],
                "cells_with_population": stats[1],
                "min_population": float(stats[2]) if stats[2] else 0,
                "max_population": float(stats[3]) if stats[3] else 0,
                "avg_population": float(stats[4]) if stats[4] else 0,
                "total_population": float(stats[5]) if stats[5] else 0,
            }
            results["updated"] = updated

        results["status"] = "success"
        debug.success(
            "population", "Population calculated", values=results["stats"], start_time=t
        )

    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)
        debug.error("population", f"Population calculation failed: {str(e)}")

    return results


def _run_pub_pipeline(run_id: str, config: dict, debug: DebugLogger) -> dict:
    """
    PUB pipeline: VORONOI grid + area-rank risk.
