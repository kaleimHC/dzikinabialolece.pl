"""
Fast-mode views (FAST pipeline - square grid, heuristic risk).
"""

import json
from datetime import date, datetime

from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from analytics.permissions import PipelineRunThrottle

from .models import ModelPrediction


@api_view(["GET"])
def grid_cells(request):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                grid_id,
                COALESCE(sighting_count, 0) as sighting_count,
                ST_AsGeoJSON(geometry) as geojson,
                COALESCE(ensemble_risk, 0.05) as ensemble_risk,
                COALESCE(confidence, 0.2) as confidence,
                COALESCE(area_rank_score, 0) as area_rank_score,
                COALESCE(gwr_score, 0) as gwr_score,
                ST_Area(geometry::geography) / 1000000.0 as area_km2
            FROM sightings_gridcell_square
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
                    "risk_source": "heuristic",
                    "grid_type": "square",
                },
            }
        )

    return Response(
        {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "mode": "fast",
                "grid_type": "square",
                "cell_count": len(features),
            },
        }
    )


@api_view(["GET"])
def risk_heatmap(request):
    # Validate `date`: a malformed string would raise Django's ValidationError
    # deep in the ORM filter (DRF's default handler does NOT catch it -> 500).
    # Parse here so a bad value is a clean 400.
    date_raw = request.query_params.get("date")
    if date_raw:
        try:
            date_param = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid date. Expected ISO format YYYY-MM-DD."},
                status=400,
            )
    else:
        date_param = date.today()

    # Allowlist `model` against known model types so a fuzzed value cannot reach
    # the DB as an arbitrary string.
    model_type = request.query_params.get("model", "ensemble")
    valid_models = {c[0] for c in ModelPrediction.ModelType.choices}
    if model_type not in valid_models:
        return Response(
            {"error": f"Invalid model. Allowed: {', '.join(sorted(valid_models))}"},
            status=400,
        )

    predictions = ModelPrediction.objects.filter(
        prediction_date=date_param, model_type=model_type
    ).select_related("grid_cell")[:5000]

    features = []
    for pred in predictions:
        if pred.grid_cell and pred.grid_cell.geometry:
            features.append(
                {
                    "type": "Feature",
                    "geometry": json.loads(pred.grid_cell.geometry.json),
                    "properties": {
                        "risk": pred.prediction_value,
                        "confidence_lower": pred.confidence_lower,
                        "confidence_upper": pred.confidence_upper,
                        "grid_id": pred.grid_cell.grid_id,
                        "sighting_count": pred.grid_cell.sighting_count,
                    },
                }
            )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def predictions_list(request):
    return Response(
        {
            "status": "ok",
            "predictions": [],
            "message": "Predictions endpoint - to be implemented",
        }
    )


# Security: whitelist for recalculate modes
ALLOWED_RECALC_MODES = {"fast"}


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PipelineRunThrottle])
def recalculate(request):
    from .tasks import recalculate_risk_model

    mode = request.query_params.get("mode", "fast")

    if mode not in ALLOWED_RECALC_MODES:
        return Response(
            {
                "status": "error",
                "message": f"Invalid mode. Allowed: {', '.join(ALLOWED_RECALC_MODES)}",
            },
            status=400,
        )

    LOCK_KEY = "recalculate_lock"
    LOCK_TIMEOUT = 600

    if not cache.add(LOCK_KEY, mode, LOCK_TIMEOUT):
        progress = cache.get("r_pipeline_progress", {})
        return Response(
            {
                "status": "already_running",
                "message": "Przeliczanie już działa",
                "current_step": progress.get("current_step", 0),
                "total_steps": progress.get("total_steps", 5),
                "mode": cache.get(LOCK_KEY, "unknown"),
            },
            status=409,
        )

    try:
        cache.set(
            "r_pipeline_progress",
            {
                "running": True,
                "current_step": 0,
                "total_steps": 4,
                "current_script": "Uruchamianie (FAST)...",
                "error": None,
                "completed": False,
            },
            timeout=3600,
        )

        recalculate_risk_model.delay()

        return Response(
            {
                "status": "started",
                "message": "Przeliczanie FAST uruchomione",
                "total_steps": 4,
                "mode": "fast",
            }
        )
    except Exception:
        cache.delete(LOCK_KEY)
        raise


@api_view(["GET"])
def recalculate_status(request):
    progress = cache.get(
        "r_pipeline_progress",
        {
            "running": False,
            "current_step": 0,
            "total_steps": 4,
            "current_script": "",
            "error": None,
            "completed": False,
        },
    )

    return Response(
        {
            "running": progress.get("running", False),
            "current_step": progress.get("current_step", 0),
            "total_steps": progress.get("total_steps", 5),
            "current_script": progress.get("current_script", ""),
            "error": progress.get("error"),
            "completed": progress.get("completed", False),
        }
    )
