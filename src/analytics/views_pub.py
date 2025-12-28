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
