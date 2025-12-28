"""
MODE ROUTER - FAST/PUB pipeline dispatcher.
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
            # Reset and count sightings per SQUARE cell
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

            # Simple risk based on sighting count
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

            # Spatial smoothing for neighbors of hot cells
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

            # Update timestamp
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

    IZOLACJA: Tylko VORONOI grid, NIE dotyka SQUARE (FAST mode).

    Pipeline steps:
    1. 01_generate_voronoi.R - Generate Voronoi cells from sightings
    2. _calculate_osm_features() - Calculate OSM environmental features (Python/SQL)
    3. _calculate_population() - Area-weighted population from GUS 500m grid (Python/SQL)
    4. 03_inverse_area_risk.R - Inverse area risk (area-rank, D-01)
    5. 05_ensemble_prediction.R - Ensemble prediction
    """
    import docker
    import os

    grid_type = config["grid_type"]  # 'voronoi'
    results = {"mode": "PUB", "grid_type": grid_type, "steps": {}}

    # D-05: 02_spatial_models.R removed from PUB - it always fails (no RESEARCH_TARGET_TABLE)
    # and its output is overwritten by 03_inverse_area_risk.R anyway (D-01).
    r_scripts = [
        ("01_generate_voronoi.R", "Generate Voronoi from current sightings"),
        ("03_inverse_area_risk.R", "Inverse area risk"),
        ("05_ensemble_prediction.R", "Ensemble prediction"),
    ]

    t = debug.start(
        "pub_pipeline",
        "PUB: Running pipeline (3 R scripts + OSM features + population)",
    )

    try:
        # Initialize Docker client
        client = docker.from_env()
        client.ping()
        debug.info("docker", "Docker connected")

        step_num = 0
        failed_steps = []

        for i, (script, description) in enumerate(r_scripts, 1):
            step_num += 1
            t_step = debug.start(f"step{step_num}", f"{description} ({script})")

            try:
                # Run R script via Docker
                # Mount r_scripts from host to get latest version
                # Use HOST_PROJECT_PATH env var (set in docker-compose.yml)
                host_project_path = os.environ.get("HOST_PROJECT_PATH", "/opt/dziki")
                r_scripts_path = f"{host_project_path}/r_scripts"
                client.containers.run(
                    "dziki-worker-r:latest",
                    command=["Rscript", "--vanilla", f"/app/r_scripts/{script}"],
                    environment={
                        "DB_HOST": "db",
                        "DB_PORT": "5432",
                        "DB_NAME": os.environ.get("DB_NAME", "dziki_db"),
                        "DB_USER": os.environ.get("DB_USER", "dziki"),
                        "DB_PASSWORD": os.environ.get(
                            "DB_PASSWORD", "dziki_dev_password"
                        ),
                        "OMP_NUM_THREADS": "1",
                    },
                    network="dziki_dziki-internal",
                    volumes={
                        "dziki_r_data": {"bind": "/app/data", "mode": "rw"},
                        r_scripts_path: {"bind": "/app/r_scripts", "mode": "ro"},
                    },
                    remove=True,
                    detach=False,
                    stdout=True,
                    stderr=True,
                )

                results["steps"][script] = "success"
                debug.success(
                    f"step{step_num}", f"{script} completed", start_time=t_step
                )

                if script == "01_generate_voronoi.R":
                    step_num += 1
                    osm_result = _calculate_osm_features(debug)
                    results["steps"]["osm_features"] = osm_result.get(
                        "status", "unknown"
                    )
                    if osm_result.get("stats"):
                        results["osm_stats"] = osm_result["stats"]

                    # Area-weighted population from GUS 500m grid
                    step_num += 1
                    pop_result = _calculate_population(debug)
                    results["steps"]["population"] = pop_result.get("status", "unknown")
                    if pop_result.get("stats"):
                        results["population_stats"] = pop_result["stats"]

            except docker.errors.ContainerError as e:
                stderr = e.stderr.decode("utf-8")[:300] if e.stderr else str(e)
                results["steps"][script] = f"error: {stderr}"
                failed_steps.append(script)
                logger.error(
                    "[PUB] Step %s FAILED (ContainerError): %s",
                    script,
                    stderr[:300],
                )
                debug.error(f"step{step_num}", f"{script} failed: {stderr}")

            except Exception as e:
                results["steps"][script] = f"error: {str(e)}"
                failed_steps.append(script)
                logger.error(
                    "[PUB] Step %s FAILED (%s): %s",
                    script,
                    type(e).__name__,
                    str(e)[:300],
                )
                debug.error(f"step{step_num}", f"{script} error: {str(e)}")

        # Get final stats from VORONOI
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*),
                       COUNT(DISTINCT ROUND(ensemble_risk::numeric, 4)),
                       MIN(ensemble_risk), MAX(ensemble_risk),
                       COUNT(*) FILTER (WHERE ensemble_risk >= 0.7)
                FROM sightings_gridcell_voronoi
                WHERE ensemble_risk IS NOT NULL
            """)
            total, unique, min_risk, max_risk, critical = cursor.fetchone()

        results["ensemble"] = {
            "count": total,
            "unique_values": unique,
            "min": round(float(min_risk), 4) if min_risk else None,
            "max": round(float(max_risk), 4) if max_risk else None,
            "critical_cells": critical,
        }

        if failed_steps:
            results["status"] = "partial_success"
            results["failed_steps"] = failed_steps
            logger.warning(
                "[PUB] Pipeline completed with %d failed step(s): %s",
                len(failed_steps),
                ", ".join(failed_steps),
            )
            debug.success(
                "pub_pipeline",
                f"PUB completed (partial - {len(failed_steps)} step(s) failed)",
                values=results["ensemble"],
                start_time=t,
            )
        else:
            results["status"] = "success"
            debug.success(
                "pub_pipeline", "PUB completed", values=results["ensemble"], start_time=t
            )

    except docker.errors.DockerException as e:
        debug.error("docker", f"Docker error: {str(e)}")
        results["status"] = "error"
        results["error"] = f"Docker: {str(e)}"

    except Exception as e:
        debug.error("pub_pipeline", f"PUB failed: {str(e)}")
        results["status"] = "error"
        results["error"] = str(e)

    return results


