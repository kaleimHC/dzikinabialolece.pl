"""
Admin/infrastructure views (OSM layers, samples, config, pipeline).
"""

import json
import logging

from django.core.cache import cache
from django.db import connection
from django_celery_results.models import TaskResult
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from analytics.permissions import PipelineRunThrottle, SamplesSwitchThrottle
from analytics.sql_injection_patch import validate_grid_type

logger = logging.getLogger(__name__)


@api_view(["GET"])
def boundaries(request):
    name = request.query_params.get("name")

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
