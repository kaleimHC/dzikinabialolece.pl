"""
Admin/infrastructure views (OSM layers, samples, config, pipeline).
"""

import json
import logging

from django.core.cache import cache
from django.db import OperationalError, ProgrammingError, connection
from django_celery_results.models import TaskResult
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from analytics.permissions import (
    IsBearerAuthenticated,
    PipelineRunThrottle,
    SamplesSwitchThrottle,
)

logger = logging.getLogger(__name__)


@api_view(["GET"])
def boundaries(request):
    name = request.query_params.get("name")

    try:
        with connection.cursor() as cursor:
            if name:
                cursor.execute(
                    """
                    SELECT name, ST_AsGeoJSON(geom) as geojson
                    FROM boundaries
                    WHERE name = %s
                """,
                    [name],
                )
            else:
                cursor.execute("""
                    SELECT name, ST_AsGeoJSON(geom) as geojson
                    FROM boundaries
                """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("boundaries: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for name, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"name": name},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def task_status(request):
    task_id = request.query_params.get("task_id")

    if not task_id:
        recent = TaskResult.objects.order_by("-date_created")[:10]
        return Response(
            {
                "recent_tasks": [
                    {
                        "task_id": t.task_id,
                        "task_name": t.task_name,
                        "status": t.status,
                        "date_created": t.date_created,
                    }
                    for t in recent
                ]
            }
        )

    try:
        result = TaskResult.objects.get(task_id=task_id)
        return Response(
            {
                "task_id": result.task_id,
                "task_name": result.task_name,
                "status": result.status,
                "result": result.result,
                "date_created": result.date_created,
                "date_done": result.date_done,
            }
        )
    except TaskResult.DoesNotExist:
        return Response(
            {
                "task_id": task_id,
                "status": "PENDING",
                "message": "Task not found or still pending",
            }
        )


@api_view(["GET"])
def buildings(request):
    bbox = request.query_params.get("bbox")

    try:
        with connection.cursor() as cursor:
            if bbox:
                try:
                    minx, miny, maxx, maxy = map(float, bbox.split(","))
                    cursor.execute(
                        """
                        SELECT osm_id, ST_AsGeoJSON(geom) as geojson
                        FROM osm_buildings
                        WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                        LIMIT 50000
                    """,
                        [minx, miny, maxx, maxy],
                    )
                except (ValueError, TypeError):
                    return Response({"error": "Invalid bbox format"}, status=400)
            else:
                cursor.execute("""
                    SELECT osm_id, ST_AsGeoJSON(geom) as geojson
                    FROM osm_buildings
                    LIMIT 50000
                """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("buildings: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"osm_id": osm_id},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def forests(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT osm_id, ST_AsGeoJSON(geom) as geojson
                FROM osm_forests
                LIMIT 10000
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("forests: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"osm_id": osm_id, "type": "forest"},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def population(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT code, tot, ST_AsGeoJSON(geom) as geojson
                FROM gus_population_grid_500m
                ORDER BY tot DESC
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("population: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for code, tot, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"code": code, "tot": tot},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def water(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT osm_id, name, ST_AsGeoJSON(geom) as geojson
                FROM osm_water
                WHERE ST_GeometryType(geom) = 'ST_Polygon'
                LIMIT 5000
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("water: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, name, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"osm_id": osm_id, "name": name, "type": "water"},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def waterways(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT osm_id, name, waterway, ST_AsGeoJSON(geom) as geojson
                FROM osm_water
                WHERE ST_GeometryType(geom) = 'ST_LineString'
                LIMIT 5000
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("waterways: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, name, waterway, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"osm_id": osm_id, "name": name, "waterway": waterway},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def barriers(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT osm_id, barrier_type, permeability, ST_AsGeoJSON(geom) as geojson
                FROM osm_barriers
                WHERE barrier_type IN ('fence', 'wall', 'retaining_wall', 'guard_rail')
                LIMIT 20000
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("barriers: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, barrier_type, permeability, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {
                    "osm_id": osm_id,
                    "type": barrier_type,
                    "permeability": permeability,
                },
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def roads(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT osm_id, highway, name, ST_AsGeoJSON(geom) as geojson
                FROM osm_roads
                LIMIT 25000
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("roads: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, highway, name, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"osm_id": osm_id, "highway": highway, "name": name},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def allotments(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT osm_id, name, ST_AsGeoJSON(geom) as geojson
                FROM osm_allotments
                LIMIT 5000
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("allotments: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, name, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"osm_id": osm_id, "name": name, "type": "allotment"},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def meadows(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT osm_id, ST_AsGeoJSON(geom) as geojson
                FROM osm_meadow
                LIMIT 5000
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("meadows: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"osm_id": osm_id, "type": "meadow"},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def farmland(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT osm_id, ST_AsGeoJSON(geom) as geojson
                FROM osm_farmland
                LIMIT 5000
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("farmland: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"osm_id": osm_id, "type": "farmland"},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def parks(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT osm_id, name, ST_AsGeoJSON(geom) as geojson
                FROM osm_parks
                LIMIT 5000
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("parks: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, name, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"osm_id": osm_id, "name": name, "type": "park"},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def scrub(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT osm_id, ST_AsGeoJSON(geom) as geojson
                FROM osm_scrub
                LIMIT 10000
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("scrub: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"osm_id": osm_id, "type": "scrub"},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


@api_view(["GET"])
def railway(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT osm_id, name, ST_AsGeoJSON(geom) as geojson
                FROM osm_railway
                LIMIT 5000
            """)
            rows = cursor.fetchall()
    except (ProgrammingError, OperationalError):
        logger.warning("railway: source table not initialized")
        return Response({"type": "FeatureCollection", "features": []})

    features = []
    for osm_id, name, geojson in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {"osm_id": osm_id, "name": name, "type": "railway"},
            }
        )

    return Response({"type": "FeatureCollection", "features": features})


VALID_SAMPLES = {
    "mala": {"n": 100, "file": "baza_mala.json"},
    "srednia": {"n": 500, "file": "baza_srednia.json"},
    "duza": {"n": 1500, "file": "baza_duza.json"},
    "pelna": {"n": 3500, "file": "baza_ogromna.json"},
}


@api_view(["GET"])
def samples_current(request):
    from sightings.models import Sighting

    count = Sighting.objects.filter(status="verified").count()

    current_sample = "unknown"
    for sample_id, info in VALID_SAMPLES.items():
        if abs(count - info["n"]) < 50:
            current_sample = sample_id
            break

    return Response(
        {
            "current_sample": current_sample,
            "sighting_count": count,
            "available_samples": list(VALID_SAMPLES.keys()),
        }
    )


# Public portfolio sandbox: visitors may switch the active sample dataset.
# switch_sample_task TRUNCATEs and reloads SYNTHETIC demo data (not real
# crowdsourced reports), so anonymous access is intentional and resetting the
# sample is a feature, not a vulnerability. Throttled to deter abuse.
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([SamplesSwitchThrottle])
def samples_switch(request):
    from .tasks import switch_sample_task

    sample = request.data.get("sample")

    if sample not in VALID_SAMPLES:
        return Response(
            {"error": f"Invalid sample. Valid: {list(VALID_SAMPLES.keys())}"},
            status=400,
        )

    progress = cache.get("sample_switch_progress", {})
    if progress.get("running"):
        return Response(
            {
                "status": "already_running",
                "message": "Przełączanie już trwa",
            },
            status=409,
        )

    task = switch_sample_task.delay(sample)

    cache.set(
        "sample_switch_progress",
        {
            "running": True,
            "task_id": task.id,
            "sample": sample,
            "current": 0,
            "total": 4,
            "step": "starting",
            "message": "Uruchamianie...",
        },
        timeout=600,
    )

    return Response(
        {
            "task_id": task.id,
            "sample": sample,
            "expected_n": VALID_SAMPLES[sample]["n"],
        }
    )


@api_view(["GET"])
def sample_task_progress(request, task_id):
    progress = cache.get("sample_switch_progress", {})

    if progress.get("task_id") != task_id:
        try:
            result = TaskResult.objects.get(task_id=task_id)
            return Response(
                {
                    "status": result.status,
                    "result": result.result,
                }
            )
        except TaskResult.DoesNotExist:
            return Response(
                {
                    "status": "PENDING",
                    "message": "Task not found",
                }
            )

    return Response(
        {
            "status": "PROGRESS" if progress.get("running") else "SUCCESS",
            "current": progress.get("current", 0),
            "total": progress.get("total", 4),
            "percent": int(progress.get("current", 0) / progress.get("total", 4) * 100),
            "step": progress.get("step", ""),
            "message": progress.get("message", ""),
            "error": progress.get("error"),
        }
    )


@api_view(["GET"])
def presets_list(request):
    from .models_config import PRESET_PROFILES

    presets = []
    for key, preset in PRESET_PROFILES.items():
        presets.append(
            {
                "id": key,
                "name": preset.get("name", key),
                "description": preset.get("description", ""),
            }
        )

    return Response(
        {
            "presets": presets,
            "count": len(presets),
        }
    )


@api_view(["POST"])
@permission_classes([IsBearerAuthenticated])
def apply_preset(request):
    from .models_config import PRESET_PROFILES, ParameterConfiguration

    preset_name = request.data.get("preset")
    activate = request.data.get("activate", True)

    if not preset_name:
        return Response({"error": 'Missing "preset" field'}, status=400)

    if preset_name not in PRESET_PROFILES:
        return Response(
            {
                "error": f"Unknown preset: {preset_name}",
                "valid_presets": list(PRESET_PROFILES.keys()),
            },
            status=400,
        )

    try:
        preset = PRESET_PROFILES[preset_name]

        existing = ParameterConfiguration.objects.filter(
            name__iexact=preset.get("name", preset_name)
        ).first()

        if existing:
            existing.apply_preset(preset_name)
            existing.is_active = activate
            existing.full_clean()
            existing.save()
            config = existing
            action = "Updated"
        else:
            config = ParameterConfiguration.create_from_preset(
                preset_name, activate=activate
            )
            action = "Created"

        return Response(
            {
                "status": "success",
                "message": f"{action} configuration from preset: {preset_name}",
                "config": {
                    "id": config.pk,
                    "name": config.name,
                    "description": config.description,
                    "is_active": config.is_active,
                },
            }
        )

    except Exception:
        logger.exception("apply_preset failed for preset=%s", preset_name)
        return Response({"error": "Internal server error applying preset"}, status=500)


@api_view(["GET"])
def active_config(request):
    from .models_config import ParameterConfiguration

    config = ParameterConfiguration.get_active()

    if config:
        return Response(
            {
                "has_active_config": True,
                "config": {
                    "id": config.pk,
                    "name": config.name,
                    "description": config.description,
                    "updated_at": config.updated_at.isoformat(),
                },
            }
        )
    else:
        return Response(
            {
                "has_active_config": False,
                "config": None,
                "message": "No active configuration in database",
            }
        )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PipelineRunThrottle])
def run_mode_pipeline(request):
    from .mode_router import MODE_CONFIG, run_pipeline

    mode = request.data.get("mode", "FAST").upper()
    run_async = request.data.get("async", False)

    if mode not in MODE_CONFIG:
        return Response(
            {
                "status": "error",
                "message": f"Invalid mode: {mode}",
                "valid_modes": list(MODE_CONFIG.keys()),
            },
            status=400,
        )

    config = MODE_CONFIG[mode]

    if run_async:
        try:
            task = run_pipeline.delay(mode=mode)
        except Exception as exc:
            logger.exception("run_pipeline.delay() failed for mode=%s", mode)
            return Response(
                {"status": "error", "mode": mode, "message": f"Task dispatch failed: {exc}"},
                status=503,
            )

        cache.set(
            f"pipeline_task:{task.id}",
            {
                "task_id": task.id,
                "mode": mode,
                "status": "queued",
            },
            timeout=3600,
        )

        return Response(
            {
                "status": "queued",
                "task_id": task.id,
                "mode": mode,
                "config": config,
                "message": f"{mode} pipeline started (async)",
            }
        )
    else:
        try:
            result = run_pipeline(mode=mode)
            return Response(
                {
                    "status": result.get("status", "unknown"),
                    "mode": mode,
                    "config": config,
                    "result": result,
                }
            )
        except Exception:
            logger.exception(
                "run_mode_pipeline sync execution failed for mode=%s", mode
            )
            return Response(
                {
                    "status": "error",
                    "mode": mode,
                    "message": "Internal server error during pipeline execution",
                },
                status=500,
            )


@api_view(["GET"])
def pipeline_status(request, task_id):
    cached = cache.get(f"pipeline_task:{task_id}")
    if cached:
        try:
            result = TaskResult.objects.get(task_id=task_id)
            if result.status == "SUCCESS":
                return Response(
                    {
                        "status": "success",
                        "task_id": task_id,
                        "mode": cached.get("mode"),
                        "result": result.result,
                    }
                )
            elif result.status == "FAILURE":
                return Response(
                    {
                        "status": "error",
                        "task_id": task_id,
                        "mode": cached.get("mode"),
                        "error": str(result.result),
                    }
                )
            else:
                return Response(
                    {
                        "status": "running",
                        "task_id": task_id,
                        "mode": cached.get("mode"),
                    }
                )
        except TaskResult.DoesNotExist:
            return Response(
                {
                    "status": "running",
                    "task_id": task_id,
                    "mode": cached.get("mode"),
                }
            )

    return Response(
        {
            "status": "not_found",
            "task_id": task_id,
            "message": "Task not found",
        },
        status=404,
    )


@api_view(["GET"])
def pipeline_modes(request):
    from .mode_router import MODE_CONFIG

    return Response(
        {
            "modes": MODE_CONFIG,
            "default": "FAST",
        }
    )
