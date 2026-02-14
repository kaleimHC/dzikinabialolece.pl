"""
Publication-mode views (PUB pipeline — Voronoi, spatial regression results, ETA).
"""

import json
import logging

from django.core.cache import cache
from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.response import Response

from analytics.sql_injection_patch import validate_grid_type, validate_limit

logger = logging.getLogger(__name__)


@api_view(["GET"])
def voronoi_cells(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                grid_id,
                COALESCE(sighting_count, 0) as sighting_count,
                ST_AsGeoJSON(geometry) as geojson,
                COALESCE(ensemble_risk, 0) as ensemble_risk,
                COALESCE(confidence, 0.5) as confidence,
                COALESCE(area_rank_score, 0) as area_rank_score,
                COALESCE(spatial_risk, gwr_score, 0) as gwr_score,
                ST_Area(geometry::geography) / 1000000.0 as area_km2
            FROM sightings_gridcell_voronoi
            WHERE geometry IS NOT NULL
            ORDER BY grid_id
        """)
        rows = cursor.fetchall()

    features = []
    for (
        grid_id,
        sighting_count,
        geojson,
        ensemble_risk,
        confidence,
        area_rank_score,
        gwr_score,
        area_km2,
    ) in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {
                    "grid_id": grid_id,
                    "sighting_count": sighting_count,
                    "risk": round(ensemble_risk, 3),
                    "confidence": round(confidence, 3),
                    "area_rank_score": round(area_rank_score, 3),
                    "gwr_score": round(gwr_score, 3),
                    "area_km2": round(area_km2, 4) if area_km2 else 0,
                    "risk_source": "ensemble",
                    "grid_type": "voronoi",
                },
            }
        )

    return Response(
        {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "mode": "publication",
                "grid_type": "voronoi",
                "cell_count": len(features),
            },
        }
    )


@api_view(["GET"])
def research_grid_cells(request):
    run_id = request.query_params.get("run_id")

    with connection.cursor() as cursor:
        query = """
            SELECT
                grid_id,
                COALESCE(sighting_count, 0) as sighting_count,
                ST_AsGeoJSON(geometry) as geojson,
                COALESCE(ensemble_risk, 0) as ensemble_risk,
                COALESCE(confidence, 0.5) as confidence,
                COALESCE(area_rank_score, 0) as area_rank_score,
                COALESCE(spatial_risk, 0) as spatial_risk,
                ST_Area(geometry::geography) / 1000000.0 as area_km2,
                COALESCE(population, 0) as population,
                y_inv_pop,
                y_log_pop,
                y_count_pop,
                y_binary,
                y_log_count,
                model_fitted,
                run_id,
                COALESCE(regime, 'mixed') as regime
            FROM sightings_gridcell_research
            WHERE geometry IS NOT NULL
        """
        params = []

        if run_id:
            query += " AND run_id = %s"
            params.append(run_id)

        query += " ORDER BY grid_id"

        cursor.execute(query, params)
        rows = cursor.fetchall()

    features = []
    for row in rows:
        (
            grid_id,
            sighting_count,
            geojson,
            ensemble_risk,
            confidence,
            area_rank_score,
            spatial_risk,
            area_km2,
            population,
            y_inv_pop,
            y_log_pop,
            y_count_pop,
            y_binary,
            y_log_count,
            model_fitted,
            row_run_id,
            regime,
        ) = row

        # FIXED 2026-01-29: Use model_fitted as primary risk source
        # model_fitted = SEM/SAR prediction based on predictors + spatial neighbors
        # Fallback chain: model_fitted -> y_log_count/spatial_risk -> ensemble_risk
        MAX_Y_LOG_COUNT = 2.5  # ln(12) ≈ 2.48
        if model_fitted is not None and model_fitted > 0:
            display_risk = model_fitted
        elif y_log_count is not None and y_log_count > 0:
            display_risk = min(y_log_count / MAX_Y_LOG_COUNT, 1.0)
        elif spatial_risk is not None and spatial_risk > 0:
            display_risk = min(spatial_risk / MAX_Y_LOG_COUNT, 1.0)
        else:
            display_risk = ensemble_risk if ensemble_risk else 0.05

        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {
                    "grid_id": grid_id,
                    "sighting_count": sighting_count,
                    # NOTE: Use "is not None" because 0 is a valid risk value (no sightings)!
                    "risk": round(display_risk, 3) if display_risk is not None else 0.5,
                    "ensemble_risk": round(ensemble_risk, 3),
                    "confidence": round(confidence, 3),
                    "area_rank_score": round(area_rank_score, 3),
                    "spatial_risk": round(spatial_risk, 3)
                    if spatial_risk is not None
                    else 0,
                    "area_km2": round(area_km2, 4) if area_km2 else 0,
                    "population": round(population, 1) if population else 0,
                    "y_formula": {
                        "inv_pop": round(y_inv_pop, 6) if y_inv_pop else None,
                        "log_pop": round(y_log_pop, 4) if y_log_pop else None,
                        "count_pop": round(y_count_pop, 6) if y_count_pop else None,
                        "log_count": round(y_log_count, 4) if y_log_count else None,
                        "binary": y_binary,
                    },
                    "model_fitted": round(model_fitted, 4) if model_fitted else None,
                    "regime": regime,
                    "risk_source": "research",
                    "grid_type": "research",
                    "run_id": row_run_id,
                },
            }
        )

    return Response(
        {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "mode": "research",
                "grid_type": "research",
                "cell_count": len(features),
                "run_id": run_id,
            },
        }
    )


@api_view(["GET"])
def research_grid_500(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                grid_id,
                COALESCE(sighting_count, 0) as sighting_count,
                ST_AsGeoJSON(geometry) as geojson,
                COALESCE(ensemble_risk, 0.05) as ensemble_risk,
                COALESCE(spatial_risk, 0) as spatial_risk,
                ST_Area(geometry::geography) / 1000000.0 as area_km2,
                COALESCE(population, 0) as population,
                COALESCE(forest_cover, 0) as forest_cover,
                COALESCE(building_density, 0) as building_density,
                COALESCE(road_density, 0) as road_density,
                y_log_pop,
                model_fitted
            FROM research_grid_500m
            WHERE geometry IS NOT NULL
            ORDER BY grid_id
        """)
        rows = cursor.fetchall()

    features = []
    for row in rows:
        (
            grid_id,
            sighting_count,
            geojson,
            ensemble_risk,
            spatial_risk,
            area_km2,
            population,
            forest_cover,
            building_density,
            road_density,
            y_log_pop,
            model_fitted,
        ) = row

        # FIXED 2026-01-29: Use model_fitted as primary risk source
        # model_fitted = SEM/SAR prediction based on predictors + spatial neighbors
        # Fallback chain: model_fitted -> spatial_risk -> ensemble_risk
        if model_fitted is not None and model_fitted > 0:
            display_risk = model_fitted
        elif spatial_risk is not None and spatial_risk > 0:
            MAX_Y_LOG_COUNT = 2.5
            display_risk = min(spatial_risk / MAX_Y_LOG_COUNT, 1.0)
        else:
            display_risk = ensemble_risk if ensemble_risk else 0.05

        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {
                    "grid_id": grid_id,
                    "sighting_count": sighting_count,
                    # NOTE: Use "is not None" because 0 is a valid risk value (no sightings)!
                    "risk": round(display_risk, 3) if display_risk is not None else 0.5,
                    "ensemble_risk": round(ensemble_risk, 3),
                    "spatial_risk": round(spatial_risk, 3)
                    if spatial_risk is not None
                    else 0,
                    "area_km2": round(area_km2, 4) if area_km2 else 0,
                    "population": round(population, 1) if population else 0,
                    "forest_cover": round(forest_cover, 4) if forest_cover else 0,
                    "building_density": round(building_density, 4)
                    if building_density
                    else 0,
                    "road_density": round(road_density, 4) if road_density else 0,
                    "y_log_pop": round(y_log_pop, 4) if y_log_pop else None,
                    "model_fitted": round(model_fitted, 4) if model_fitted else None,
                    "risk_source": "research",
                    "grid_type": "grid_500",
                },
            }
        )

    return Response(
        {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "mode": "research",
                "grid_type": "grid_500",
                "cell_count": len(features),
            },
        }
    )


@api_view(["POST"])
def calculate_voronoi_features(request):
    results = {
        "distance_to_forest": {"updated": 0, "error": None},
        "distance_to_water": {"updated": 0, "error": None},
        "forest_cover": {"updated": 0, "error": None},
        "building_density": {"updated": 0, "error": None},
        "road_density": {"updated": 0, "error": None},
    }

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM sightings_gridcell_voronoi")
        cell_count = cursor.fetchone()[0]
        if cell_count == 0:
            return Response(
                {
                    "status": "error",
                    "message": "No Voronoi cells found. Run 01_generate_voronoi.R first.",
                },
                status=400,
            )

        logger.info(f"Calculating features for {cell_count} Voronoi cells...")

        try:
            cursor.execute("SELECT COUNT(*) FROM osm_forests")
            forest_count = cursor.fetchone()[0]
            logger.info(f"  osm_forests: {forest_count} rows")

            if forest_count > 0:
                cursor.execute("""
                    UPDATE sightings_gridcell_voronoi g
                    SET distance_to_forest = subq.dist
                    FROM (
                        SELECT DISTINCT ON (gc.id)
                            gc.id,
                            ST_Distance(
                                ST_Transform(gc.geometry, 2180),
                                ST_Transform(f.geom, 2180)
                            ) as dist
                        FROM sightings_gridcell_voronoi gc
                        CROSS JOIN LATERAL (
                            SELECT geom
                            FROM osm_forests
                            ORDER BY gc.geometry <-> geom
                            LIMIT 1
                        ) f
                    ) subq
                    WHERE g.id = subq.id;
                """)
                results["distance_to_forest"]["updated"] = cursor.rowcount
                logger.info(f"  distance_to_forest: {cursor.rowcount} updated")
        except Exception as e:
            results["distance_to_forest"]["error"] = str(e)
            logger.error(f"  distance_to_forest ERROR: {e}")

        try:
            cursor.execute("SELECT COUNT(*) FROM osm_water")
            water_count = cursor.fetchone()[0]
            logger.info(f"  osm_water: {water_count} rows")

            if water_count > 0:
                cursor.execute("""
                    UPDATE sightings_gridcell_voronoi g
                    SET distance_to_water = subq.dist
                    FROM (
                        SELECT DISTINCT ON (gc.id)
                            gc.id,
                            ST_Distance(
                                ST_Transform(gc.geometry, 2180),
                                ST_Transform(w.geom, 2180)
                            ) as dist
                        FROM sightings_gridcell_voronoi gc
                        CROSS JOIN LATERAL (
                            SELECT geom
                            FROM osm_water
                            ORDER BY gc.geometry <-> geom
                            LIMIT 1
                        ) w
                    ) subq
                    WHERE g.id = subq.id;
                """)
                results["distance_to_water"]["updated"] = cursor.rowcount
                logger.info(f"  distance_to_water: {cursor.rowcount} updated")
        except Exception as e:
            results["distance_to_water"]["error"] = str(e)
            logger.error(f"  distance_to_water ERROR: {e}")

        try:
            cursor.execute("""
                UPDATE sightings_gridcell_voronoi g
                SET forest_cover = COALESCE(subq.cover, 0)
                FROM (
                    SELECT
                        gc.id,
                        SUM(ST_Area(ST_Intersection(gc.geometry, f.geom)::geography)) /
                            NULLIF(ST_Area(gc.geometry::geography), 0) as cover
                    FROM sightings_gridcell_voronoi gc
                    LEFT JOIN osm_forests f ON ST_Intersects(gc.geometry, f.geom)
                    GROUP BY gc.id
                ) subq
                WHERE g.id = subq.id;
            """)
            results["forest_cover"]["updated"] = cursor.rowcount
            logger.info(f"  forest_cover: {cursor.rowcount} updated")
        except Exception as e:
            results["forest_cover"]["error"] = str(e)
            logger.error(f"  forest_cover ERROR: {e}")

        try:
            cursor.execute("""
                UPDATE sightings_gridcell_voronoi g
                SET building_density = COALESCE(subq.density, 0)
                FROM (
                    SELECT
                        gc.id,
                        SUM(ST_Area(ST_Intersection(gc.geometry, b.geom)::geography)) /
                            NULLIF(ST_Area(gc.geometry::geography), 0) as density
                    FROM sightings_gridcell_voronoi gc
                    LEFT JOIN osm_buildings b ON ST_Intersects(gc.geometry, b.geom)
                    GROUP BY gc.id
                ) subq
                WHERE g.id = subq.id;
            """)
            results["building_density"]["updated"] = cursor.rowcount
            logger.info(f"  building_density: {cursor.rowcount} updated")
        except Exception as e:
            results["building_density"]["error"] = str(e)
            logger.error(f"  building_density ERROR: {e}")

        try:
            cursor.execute("""
                UPDATE sightings_gridcell_voronoi g
                SET road_density = COALESCE(subq.density, 0)
                FROM (
                    SELECT
                        gc.id,
                        SUM(ST_Length(ST_Intersection(gc.geometry, r.geom)::geography)) / 1000.0 /
                            NULLIF(ST_Area(gc.geometry::geography) / 1000000.0, 0) as density
                    FROM sightings_gridcell_voronoi gc
                    LEFT JOIN osm_roads r ON ST_Intersects(gc.geometry, r.geom)
                    GROUP BY gc.id
                ) subq
                WHERE g.id = subq.id;
            """)
            results["road_density"]["updated"] = cursor.rowcount
            logger.info(f"  road_density: {cursor.rowcount} updated")
        except Exception as e:
            results["road_density"]["error"] = str(e)
            logger.error(f"  road_density ERROR: {e}")

        cursor.execute("UPDATE sightings_gridcell_voronoi SET updated_at = NOW()")

    cache.clear()

    errors = [f for f, v in results.items() if v["error"]]

    return Response(
        {
            "status": "success" if not errors else "partial",
            "cells": cell_count,
            "results": results,
            "errors": errors,
        }
    )


@api_view(["GET"])
def combined_results(request):
    grid_type = request.GET.get("grid_type", "voronoi")
    limit = validate_limit(request.GET.get("limit", 100))
    min_risk = request.GET.get("min_risk")

    try:
        grid_table = validate_grid_type(grid_type)
    except ValueError:
        return Response({"error": f"Invalid grid_type: {grid_type}"}, status=400)

    gwr_select = (
        "COALESCE(gc.spatial_risk, gc.gwr_score, 0)"
        if grid_type == "voronoi"
        else "gc.gwr_score"
    )
    query = f"""
        SELECT
            gc.id as cell_id,
            rf_mp.prediction_value as rf,
            {gwr_select} as gwr,
            gc.area_rank_score as eta,
            COALESCE(br.intensity_mean, 0) as bayesian,
            gc.ensemble_risk as ensemble,
            br.prob_above_threshold,
            br.r_hat,
            br.ess_bulk
        FROM {grid_table} gc
        LEFT JOIN analytics_modelprediction rf_mp
            ON gc.id = rf_mp.grid_cell_id AND rf_mp.model_type = 'RF'
        LEFT JOIN analytics_bayesian_result br
            ON gc.id = br.cell_id AND br.grid_type = %s
        WHERE gc.ensemble_risk IS NOT NULL
    """
    params = [grid_type]

    if min_risk:
        query += " AND gc.ensemble_risk >= %s"
        params.append(float(min_risk))

    query += f" ORDER BY gc.ensemble_risk DESC LIMIT {limit}"  # limit already validated

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    results = []
    high_risk_count = 0
    for row in rows:
        cell_id, rf, gwr, eta, bayesian, ensemble, prob_above, r_hat, ess = row
        result = {
            "cell_id": cell_id,
            "rf": float(rf) if rf else None,
            "gwr": float(gwr) if gwr else None,
            "eta": float(eta) if eta else None,
            "bayesian": float(bayesian) if bayesian else None,
            "ensemble": float(ensemble) if ensemble else None,
            "prob_above_threshold": float(prob_above) if prob_above else None,
            "r_hat": float(r_hat) if r_hat else None,
            "ess": float(ess) if ess else None,
        }
        results.append(result)
        if ensemble and float(ensemble) > 0.7:
            high_risk_count += 1

    return Response(
        {
            "results": results,
            "count": len(results),
            "high_risk_count": high_risk_count,
            "grid_type": grid_type,
        }
    )


@api_view(["GET"])
def export_results_csv(request):
    import csv

    from django.http import HttpResponse

    grid_type = request.GET.get("grid_type", "voronoi")

    try:
        grid_table = validate_grid_type(grid_type)
    except ValueError:
        return HttpResponse(f"Invalid grid_type: {grid_type}", status=400)

    gwr_select = (
        "COALESCE(gc.spatial_risk, gc.gwr_score, 0)"
        if grid_type == "voronoi"
        else "gc.gwr_score"
    )
    query = f"""
        SELECT
            gc.id as cell_id,
            rf_mp.prediction_value as rf,
            {gwr_select} as gwr,
            gc.area_rank_score as eta,
            COALESCE(br.intensity_mean, 0) as bayesian,
            gc.ensemble_risk as ensemble,
            br.prob_above_threshold,
            br.r_hat,
            br.ess_bulk
        FROM {grid_table} gc
        LEFT JOIN analytics_modelprediction rf_mp
            ON gc.id = rf_mp.grid_cell_id AND rf_mp.model_type = 'RF'
        LEFT JOIN analytics_bayesian_result br
            ON gc.id = br.cell_id AND br.grid_type = %s
        WHERE gc.ensemble_risk IS NOT NULL
        ORDER BY gc.ensemble_risk DESC
        LIMIT 5000
    """

    with connection.cursor() as cursor:
        cursor.execute(query, [grid_type])
        rows = cursor.fetchall()

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="risk_results_{grid_type}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(
        [
            "cell_id",
            "rf",
            "gwr",
            "eta",
            "bayesian",
            "ensemble",
            "prob_above_threshold",
            "r_hat",
            "ess",
        ]
    )

    for row in rows:
        writer.writerow(row)

    return response


@api_view(["GET"])
def eta_current(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH areas AS (
                SELECT
                    id,
                    ST_Area(geometry::geography) as cell_area
                FROM sightings_gridcell_voronoi
                WHERE geometry IS NOT NULL
            ),
            total AS (
                SELECT SUM(cell_area) as total_area, COUNT(*) as n_tiles
                FROM areas
            ),
            proportions AS (
                SELECT
                    a.cell_area / NULLIF(t.total_area, 0) as area_prop
                FROM areas a, total t
            ),
            entropy AS (
                SELECT
                    (SELECT n_tiles FROM total) as n_tiles,
                    -SUM(
                        CASE WHEN area_prop > 0
                        THEN area_prop * LN(area_prop)
                        ELSE 0 END
                    ) as s_ent,
                    LN((SELECT n_tiles FROM total)::float) as h_max
                FROM proportions
            )
            SELECT
                n_tiles,
                s_ent,
                h_max,
                CASE WHEN h_max > 0 THEN s_ent / h_max ELSE 0 END as h_rel
            FROM entropy
        """)
        row = cursor.fetchone()

        cursor.execute("""
            SELECT
                AVG(area_rank_score) as avg_area_rank,
                MIN(area_rank_score) as min_area_rank,
                MAX(area_rank_score) as max_area_rank,
                STDDEV(area_rank_score) as std_area_rank,
                AVG(area_proportion) as avg_area_prop
            FROM sightings_gridcell_voronoi
            WHERE area_rank_score IS NOT NULL
        """)
        stats_row = cursor.fetchone()

    if not row:
        return Response(
            {
                "error": "No Voronoi tessellation data available",
                "source": "spatialWarsaw::ETA()",
            },
            status=404,
        )

    n_tiles, s_ent, h_max, h_rel = row
    avg_area_rank, min_area_rank, max_area_rank, std_area_rank, avg_area_prop = (
        stats_row or (None,) * 5
    )

    if h_rel and h_rel > 0.9:
        interpretation = "rozkład równomierny (brak aglomeracji)"
    elif h_rel and h_rel > 0.7:
        interpretation = "lekkie skupienie"
    elif h_rel and h_rel > 0.5:
        interpretation = "umiarkowane skupienie"
    elif h_rel:
        interpretation = "silna aglomeracja"
    else:
        interpretation = "unknown"

    return Response(
        {
            "h_rel": round(float(h_rel), 4) if h_rel else None,
            "s_ent": round(float(s_ent), 4) if s_ent else None,
            "h_max": round(float(h_max), 4) if h_max else None,
            "n_tiles": n_tiles,
            "interpretation": interpretation,
            "cell_stats": {
                "avg_area_rank_score": round(float(avg_area_rank), 4)
                if avg_area_rank
                else None,
                "min_area_rank_score": round(float(min_area_rank), 4)
                if min_area_rank
                else None,
                "max_area_rank_score": round(float(max_area_rank), 4)
                if max_area_rank
                else None,
                "std_area_rank_score": round(float(std_area_rank), 4)
                if std_area_rank
                else None,
                "avg_area_proportion": round(float(avg_area_prop), 6)
                if avg_area_prop
                else None,
            },
            "source": "spatialWarsaw::ETA() — 100% zgodne",
            "reference": "spatialWarsaw::ETA() via tessellation",
        }
    )


@api_view(["GET"])
def spatial_current(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                id,
                computed_at,
                model_type,
                n_cells,
                rho,
                lambda,
                aic,
                formula
            FROM analytics_spatial_result
            ORDER BY computed_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()

    if not row:
        return Response(
            {
                "error": "No spatial model results available. Run NEW_02_spatial_models.R first.",
                "source": "spatialreg::lagsarlm/errorsarlm",
            },
            status=404,
        )

    id_, computed_at, model_type, n_cells, rho, lambda_, aic, formula = row

    if model_type == "SAR":
        description = "Spatial Autoregressive Model (lagsarlm): y = ρWy + Xβ + ε"
        spatial_param = {
            "name": "rho (ρ)",
            "value": round(float(rho), 4) if rho else None,
        }
    elif model_type == "SEM":
        description = "Spatial Error Model (errorsarlm): y = Xβ + u, u = λWu + ε"
        spatial_param = {
            "name": "lambda (λ)",
            "value": round(float(lambda_), 4) if lambda_ else None,
        }
    else:
        description = f"{model_type} model"
        spatial_param = {"name": "N/A", "value": None}

    return Response(
        {
            "model_type": model_type,
            "description": description,
            "n_cells": n_cells,
            "spatial_param": spatial_param,
            "rho": round(float(rho), 4) if rho else None,
            "lambda": round(float(lambda_), 4) if lambda_ else None,
            "aic": round(float(aic), 2) if aic else None,
            "formula": formula,
            "computed_at": computed_at.isoformat() if computed_at else None,
            "source": "spatialreg::lagsarlm/errorsarlm",
            "reference": "NEW_02_spatial_models.R",
        }
    )


@api_view(["GET"])
def w_matrix_edges(request):
    import os

    geojson_path = "/r_data/w_matrix_edges.geojson"

    if not os.path.exists(geojson_path):
        return Response(
            {
                "error": "W matrix edges not available. Run the research pipeline first.",
                "path": geojson_path,
            },
            status=404,
        )

    with open(geojson_path, "r") as f:
        geojson_data = json.load(f)

    n_edges = len(geojson_data.get("features", []))

    return Response(
        {
            "type": "FeatureCollection",
            "metadata": {
                "n_edges": n_edges,
                "description": "Spatial neighbor connections (W matrix edges)",
                "source": "research_W.rds via export_w_edges.R",
            },
            "features": geojson_data.get("features", []),
        }
    )
