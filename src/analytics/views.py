"""
Views for Analytics app.
"""

import json
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import connection
from django.core.cache import cache


@api_view(['GET'])
def grid_cells(request):
    """
    Get SQUARE grid cells as GeoJSON (FAST mode).

    GET /api/analytics/grid/
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                grid_id,
                COALESCE(sighting_count, 0) as sighting_count,
                ST_AsGeoJSON(geometry) as geojson,
                COALESCE(ensemble_risk, 0.05) as ensemble_risk,
                COALESCE(confidence, 0.2) as confidence
            FROM sightings_gridcell_square
            WHERE geometry IS NOT NULL
            ORDER BY grid_id
        """)
        rows = cursor.fetchall()

    features = []
    for grid_id, sighting_count, geojson, ensemble_risk, confidence in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {
                'grid_id': grid_id,
                'sighting_count': sighting_count,
                'risk': round(ensemble_risk, 3),
                'confidence': round(confidence, 3),
            }
        })

    return Response({
        'type': 'FeatureCollection',
        'features': features,
        'metadata': {
            'mode': 'fast',
            'cell_count': len(features),
        }
    })


@api_view(['GET'])
def boundaries(request):
    """
    Get Białołęka boundary polygon as GeoJSON.

    GET /api/analytics/boundaries/
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, ST_AsGeoJSON(geometry)
            FROM sightings_warsawboundary
            LIMIT 1
        """)
        row = cursor.fetchone()

    if not row:
        return Response({'type': 'FeatureCollection', 'features': []})

    name, geojson = row
    return Response({
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'name': name}
        }]
    })
