"""
Views for Analytics app.
"""

import json
from datetime import date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import connection
from analytics.sql_injection_patch import validate_grid_type, validate_limit
from analytics.permissions import IsBearerAuthenticated
from django.core.cache import cache
from django_celery_results.models import TaskResult

from .models import ModelPrediction


@api_view(['GET'])
def grid_cells(request):
    """
    Get SQUARE grid cells as GeoJSON (FAST mode).

    GET /api/analytics/grid/

    Table: sightings_gridcell_square
    Grid: 100x100m regular squares
    Risk: Heuristic (percentile ranking of sighting density)
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                grid_id,
                COALESCE(sighting_count, 0) as sighting_count,
                ST_AsGeoJSON(geometry) as geojson,
                COALESCE(ensemble_risk, 0.05) as ensemble_risk,
                COALESCE(confidence, 0.2) as confidence,
                COALESCE(eta_score, 0) as eta_score,
                COALESCE(gwr_score, 0) as gwr_score,
                ST_Area(geometry::geography) / 1000000.0 as area_km2
            FROM sightings_gridcell_square
            WHERE geometry IS NOT NULL
            ORDER BY grid_id
        """)
        rows = cursor.fetchall()

    features = []
    for grid_id, sighting_count, geojson, ensemble_risk, confidence, eta_score, gwr_score, area_km2 in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {
                'grid_id': grid_id,
                'sighting_count': sighting_count,
                'risk': round(ensemble_risk, 3),
                'confidence': round(confidence, 3),
                'eta_score': round(eta_score, 3),
                'gwr_score': round(gwr_score, 3),
                'area_km2': round(area_km2, 4) if area_km2 else 0,
                'risk_source': 'heuristic',
                'grid_type': 'square',
            }
        })

    return Response({
        'type': 'FeatureCollection',
        'features': features,
        'metadata': {
            'mode': 'fast',
            'grid_type': 'square',
            'cell_count': len(features),
        }
    })


@api_view(['GET'])
def voronoi_cells(request):
    """
    Get VORONOI cells as GeoJSON (PUB mode).

    GET /api/analytics/voronoi/

    Table: sightings_gridcell_voronoi
    Grid: Voronoi tessellation from sighting points
    Risk: spatialWarsaw (ETA + GWR ensemble)
    """
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
    for grid_id, sighting_count, geojson, ensemble_risk, confidence, area_rank_score, gwr_score, area_km2 in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {
                'grid_id': grid_id,
                'sighting_count': sighting_count,
                'risk': round(ensemble_risk, 3),
                'confidence': round(confidence, 3),
                'area_rank_score': round(area_rank_score, 3),
                'gwr_score': round(gwr_score, 3),
                'area_km2': round(area_km2, 4) if area_km2 else 0,
                'risk_source': 'ensemble',
                'grid_type': 'voronoi',
            }
        })

    return Response({
        'type': 'FeatureCollection',
        'features': features,
        'metadata': {
            'mode': 'publication',
            'grid_type': 'voronoi',
            'cell_count': len(features),
        }
    })


@api_view(['GET'])
def research_grid_cells(request):
    """
    Get RESEARCH grid cells as GeoJSON (RESEARCH mode).

    GET /api/analytics/research-grid/

    Table: sightings_gridcell_research
    Grid: Experimental grid for spatialWarsaw research
    Risk: Various Y formulas and model experiments
    """
    run_id = request.query_params.get('run_id')

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
        (grid_id, sighting_count, geojson, ensemble_risk, confidence,
         area_rank_score, spatial_risk, area_km2, population,
         y_inv_pop, y_log_pop, y_count_pop, y_binary, y_log_count, model_fitted, row_run_id, regime) = row

        # FIXED 2026-01-29: Use model_fitted as primary risk source
        # model_fitted = SEM/SAR prediction based on predictors + spatial neighbors
        # Fallback chain: model_fitted -> y_log_count/spatial_risk -> ensemble_risk
        MAX_Y_LOG_COUNT = 2.5  # ln(12) ≈ 2.48
        if model_fitted is not None and model_fitted > 0:
            # SEM/SAR model prediction (already normalized 0-1)
            display_risk = model_fitted
        elif y_log_count is not None and y_log_count > 0:
            display_risk = min(y_log_count / MAX_Y_LOG_COUNT, 1.0)
        elif spatial_risk is not None and spatial_risk > 0:
            display_risk = min(spatial_risk / MAX_Y_LOG_COUNT, 1.0)
        else:
            display_risk = ensemble_risk if ensemble_risk else 0.05

        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {
                'grid_id': grid_id,
                'sighting_count': sighting_count,
                # Use normalized y_log_count for color interpolation (0-1 range)
                # NOTE: Use "is not None" because 0 is a valid risk value (no sightings)!
                'risk': round(display_risk, 3) if display_risk is not None else 0.5,
                'ensemble_risk': round(ensemble_risk, 3),  # Old formula for comparison
                'confidence': round(confidence, 3),
                'area_rank_score': round(area_rank_score, 3),
                'spatial_risk': round(spatial_risk, 3) if spatial_risk is not None else 0,
                'area_km2': round(area_km2, 4) if area_km2 else 0,
                'population': round(population, 1) if population else 0,
                'y_formula': {
                    'inv_pop': round(y_inv_pop, 6) if y_inv_pop else None,
                    'log_pop': round(y_log_pop, 4) if y_log_pop else None,
                    'count_pop': round(y_count_pop, 6) if y_count_pop else None,
                    'log_count': round(y_log_count, 4) if y_log_count else None,
                    'binary': y_binary,
                },
                'model_fitted': round(model_fitted, 4) if model_fitted else None,
                'regime': regime,
                'risk_source': 'research',
                'grid_type': 'research',
                'run_id': row_run_id,
            }
        })

    return Response({
        'type': 'FeatureCollection',
        'features': features,
        'metadata': {
            'mode': 'research',
            'grid_type': 'research',
            'cell_count': len(features),
            'run_id': run_id,
        }
    })


@api_view(['GET'])
def research_grid_500(request):
    """
    Get RESEARCH grid 500m cells as GeoJSON.

    GET /api/analytics/research-grid-500/

    Table: research_grid_500m
    Grid: 500m cells aligned with GUS statistical grid
    """
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
        (grid_id, sighting_count, geojson, ensemble_risk, spatial_risk,
         area_km2, population, forest_cover, building_density, road_density,
         y_log_pop, model_fitted) = row

        # FIXED 2026-01-29: Use model_fitted as primary risk source
        # model_fitted = SEM/SAR prediction based on predictors + spatial neighbors
        # This gives risk estimates even for cells with 0 sightings (spatial spillover)
        #
        # Fallback chain: model_fitted -> spatial_risk -> ensemble_risk
        if model_fitted is not None and model_fitted > 0:
            # SEM/SAR model prediction (already normalized 0-1)
            display_risk = model_fitted
        elif spatial_risk is not None and spatial_risk > 0:
            # Raw Y value - normalize if needed (log_count max ≈ 2.5)
            MAX_Y_LOG_COUNT = 2.5
            display_risk = min(spatial_risk / MAX_Y_LOG_COUNT, 1.0)
        else:
            display_risk = ensemble_risk if ensemble_risk else 0.05

        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {
                'grid_id': grid_id,
                'sighting_count': sighting_count,
                # Use normalized spatial_risk for color interpolation (0-1 range)
                # NOTE: Use "is not None" because 0 is a valid risk value (no sightings)!
                'risk': round(display_risk, 3) if display_risk is not None else 0.5,
                'ensemble_risk': round(ensemble_risk, 3),
                'spatial_risk': round(spatial_risk, 3) if spatial_risk is not None else 0,
                'area_km2': round(area_km2, 4) if area_km2 else 0,
                'population': round(population, 1) if population else 0,
                'forest_cover': round(forest_cover, 4) if forest_cover else 0,
                'building_density': round(building_density, 4) if building_density else 0,
                'road_density': round(road_density, 4) if road_density else 0,
                'y_log_pop': round(y_log_pop, 4) if y_log_pop else None,
                'model_fitted': round(model_fitted, 4) if model_fitted else None,
                'risk_source': 'research',
                'grid_type': 'grid_500',
            }
        })

    return Response({
        'type': 'FeatureCollection',
        'features': features,
        'metadata': {
            'mode': 'research',
            'grid_type': 'grid_500',
            'cell_count': len(features),
        }
    })


@api_view(['GET'])
def risk_heatmap(request):
    """
    Get risk predictions as GeoJSON for heatmap.

    GET /api/analytics/risk/
    GET /api/analytics/risk/?date=2024-12-27&model=ensemble
    """
    date_param = request.query_params.get('date', str(date.today()))
    model_type = request.query_params.get('model', 'ensemble')

    predictions = ModelPrediction.objects.filter(
        prediction_date=date_param,
        model_type=model_type
    ).select_related('grid_cell')

    features = []
    for pred in predictions:
        if pred.grid_cell and pred.grid_cell.geometry:
            features.append({
                'type': 'Feature',
                'geometry': json.loads(pred.grid_cell.geometry.json),
                'properties': {
                    'risk': pred.prediction_value,
                    'confidence_lower': pred.confidence_lower,
                    'confidence_upper': pred.confidence_upper,
                    'grid_id': pred.grid_cell.grid_id,
                    'sighting_count': pred.grid_cell.sighting_count
                }
            })

    return Response({
        'type': 'FeatureCollection',
        'features': features
    })


@api_view(['GET'])
def predictions_list(request):
    """
    Get model predictions.

    GET /api/analytics/predictions/
    """
    # TODO: Implement predictions retrieval
    return Response({
        'status': 'ok',
        'predictions': [],
        'message': 'Predictions endpoint - to be implemented'
    })


# Security: whitelist for recalculate modes
ALLOWED_RECALC_MODES = {'fast', 'full'}


@api_view(['POST'])
@permission_classes([IsBearerAuthenticated])
def recalculate(request):
    """
    Trigger R pipeline recalculation via Celery (dev only).

    POST /api/analytics/recalculate/
    POST /api/analytics/recalculate/?mode=fast  (Python-only, ~2s)
    POST /api/analytics/recalculate/?mode=full  (R pipeline, ~2min)
    """
    from .tasks import recalculate_risk_model, run_r_pipeline_dev

    mode = request.query_params.get('mode', 'full')

    # Security: whitelist validation
    if mode not in ALLOWED_RECALC_MODES:
        return Response({
            'status': 'error',
            'message': f'Invalid mode. Allowed: {", ".join(ALLOWED_RECALC_MODES)}'
        }, status=400)

    # Atomic lock to prevent race condition
    # cache.add() returns True only if key didn't exist (atomic operation)
    LOCK_KEY = 'recalculate_lock'
    LOCK_TIMEOUT = 600  # 10 minutes max

    if not cache.add(LOCK_KEY, mode, LOCK_TIMEOUT):
        # Lock exists - check current progress for status info
        progress = cache.get('r_pipeline_progress', {})
        return Response({
            'status': 'already_running',
            'message': 'Przeliczanie już działa',
            'current_step': progress.get('current_step', 0),
            'total_steps': progress.get('total_steps', 5),
            'mode': cache.get(LOCK_KEY, 'unknown'),
        }, status=409)

    # Lock acquired - proceed with task
    try:
        if mode == 'fast':
            # Fast Python-only recalculation (~2s)
            cache.set('r_pipeline_progress', {
                'running': True,
                'current_step': 0,
                'total_steps': 4,
                'current_script': 'Uruchamianie (FAST)...',
                'error': None,
                'completed': False,
            }, timeout=3600)

            recalculate_risk_model.delay()

            return Response({
                'status': 'started',
                'message': 'Przeliczanie FAST uruchomione',
                'total_steps': 4,
                'mode': 'fast',
            })
        else:
            # Full R pipeline recalculation (~2min)
            cache.set('r_pipeline_progress', {
                'running': True,
                'current_step': 0,
                'total_steps': 5,
                'current_script': 'Uruchamianie R pipeline...',
                'error': None,
                'completed': False,
            }, timeout=3600)

            run_r_pipeline_dev.delay()

            return Response({
                'status': 'started',
                'message': 'Przeliczanie R uruchomione',
                'total_steps': 5,
                'mode': 'full',
            })
    except Exception as e:
        # Release lock on error
        cache.delete(LOCK_KEY)
        raise


@api_view(['GET'])
def recalculate_status(request):
    """
    Get R pipeline recalculation status (dev only).

    GET /api/analytics/recalculate/status/
    """
    progress = cache.get('r_pipeline_progress', {
        'running': False,
        'current_step': 0,
        'total_steps': 4,
        'current_script': '',
        'error': None,
        'completed': False,
    })

    return Response({
        'running': progress.get('running', False),
        'current_step': progress.get('current_step', 0),
        'total_steps': progress.get('total_steps', 5),
        'current_script': progress.get('current_script', ''),
        'error': progress.get('error'),
        'completed': progress.get('completed', False),
    })


@api_view(['GET'])
def boundaries(request):
    """
    Get administrative/geographic boundaries as GeoJSON.

    GET /api/analytics/boundaries/
    GET /api/analytics/boundaries/?name=bialoleka
    GET /api/analytics/boundaries/?name=wisla
    """
    name = request.query_params.get('name')

    with connection.cursor() as cursor:
        if name:
            cursor.execute("""
                SELECT name, ST_AsGeoJSON(geom) as geojson
                FROM boundaries
                WHERE name = %s
            """, [name])
        else:
            cursor.execute("""
                SELECT name, ST_AsGeoJSON(geom) as geojson
                FROM boundaries
            """)
        rows = cursor.fetchall()

    features = []
    for name, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'name': name}
        })

    return Response({
        'type': 'FeatureCollection',
        'features': features
    })


@api_view(['GET'])
def task_status(request):
    """
    Get Celery task status.

    GET /api/analytics/status/?task_id=xxx
    """
    task_id = request.query_params.get('task_id')

    if not task_id:
        # Return recent tasks
        recent = TaskResult.objects.order_by('-date_created')[:10]
        return Response({
            'recent_tasks': [
                {
                    'task_id': t.task_id,
                    'task_name': t.task_name,
                    'status': t.status,
                    'date_created': t.date_created,
                }
                for t in recent
            ]
        })

    try:
        result = TaskResult.objects.get(task_id=task_id)
        return Response({
            'task_id': result.task_id,
            'task_name': result.task_name,
            'status': result.status,
            'result': result.result,
            'date_created': result.date_created,
            'date_done': result.date_done,
        })
    except TaskResult.DoesNotExist:
        return Response({
            'task_id': task_id,
            'status': 'PENDING',
            'message': 'Task not found or still pending'
        })



@api_view(['GET'])
def buildings(request):
    """
    Get buildings as GeoJSON for map layer.
    Buildings are BARRIERS, not grid cells.

    GET /api/analytics/buildings/
    GET /api/analytics/buildings/?bbox=20.95,52.28,21.05,52.38
    """
    bbox = request.query_params.get('bbox')

    with connection.cursor() as cursor:
        if bbox:
            try:
                minx, miny, maxx, maxy = map(float, bbox.split(','))
                cursor.execute("""
                    SELECT osm_id, ST_AsGeoJSON(geom) as geojson
                    FROM osm_buildings
                    WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                    LIMIT 50000
                """, [minx, miny, maxx, maxy])
            except (ValueError, TypeError):
                return Response({'error': 'Invalid bbox format'}, status=400)
        else:
            cursor.execute("""
                SELECT osm_id, ST_AsGeoJSON(geom) as geojson
                FROM osm_buildings
                LIMIT 50000
            """)
        rows = cursor.fetchall()

    features = []
    for osm_id, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id}
        })

    return Response({
        'type': 'FeatureCollection',
        'features': features
    })


@api_view(['GET'])
def forests(request):
    """Get forests as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT osm_id, ST_AsGeoJSON(geom) as geojson
            FROM osm_forests
            LIMIT 10000
        """)
        rows = cursor.fetchall()

    features = []
    for osm_id, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id, 'type': 'forest'}
        })

    return Response({'type': 'FeatureCollection', 'features': features})


@api_view(['GET'])
def population(request):
    """Get GUS 500m population grid cells as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT code, tot, ST_AsGeoJSON(geom) as geojson
            FROM gus_population_grid_500m
            ORDER BY tot DESC
        """)
        rows = cursor.fetchall()

    features = []
    for code, tot, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'code': code, 'tot': tot}
        })

    return Response({'type': 'FeatureCollection', 'features': features})


@api_view(['GET'])
def water(request):
    """Get water bodies (polygons only) as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT osm_id, name, ST_AsGeoJSON(geom) as geojson
            FROM osm_water
            WHERE ST_GeometryType(geom) = 'ST_Polygon'
            LIMIT 5000
        """)
        rows = cursor.fetchall()

    features = []
    for osm_id, name, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id, 'name': name, 'type': 'water'}
        })

    return Response({'type': 'FeatureCollection', 'features': features})


@api_view(['GET'])
def waterways(request):
    """Get waterways (lines - rivers, streams) as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT osm_id, name, waterway, ST_AsGeoJSON(geom) as geojson
            FROM osm_water
            WHERE ST_GeometryType(geom) = 'ST_LineString'
            LIMIT 5000
        """)
        rows = cursor.fetchall()

    features = []
    for osm_id, name, waterway, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id, 'name': name, 'waterway': waterway}
        })

    return Response({'type': 'FeatureCollection', 'features': features})




@api_view(['GET'])
def barriers(request):
    """Get barriers (fences, walls) as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT osm_id, barrier_type, permeability, ST_AsGeoJSON(geom) as geojson
            FROM osm_barriers
            WHERE barrier_type IN ('fence', 'wall', 'retaining_wall', 'guard_rail')
            LIMIT 20000
        """)
        rows = cursor.fetchall()

    features = []
    for osm_id, barrier_type, permeability, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id, 'type': barrier_type, 'permeability': permeability}
        })

    return Response({'type': 'FeatureCollection', 'features': features})


@api_view(['GET'])
def roads(request):
    """Get roads as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT osm_id, highway, name, ST_AsGeoJSON(geom) as geojson
            FROM osm_roads
            LIMIT 25000
        """)
        rows = cursor.fetchall()

    features = []
    for osm_id, highway, name, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id, 'highway': highway, 'name': name}
        })

    return Response({'type': 'FeatureCollection', 'features': features})


@api_view(['GET'])
def allotments(request):
    """Get allotment gardens as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT osm_id, name, ST_AsGeoJSON(geom) as geojson
            FROM osm_allotments
            LIMIT 5000
        """)
        rows = cursor.fetchall()

    features = []
    for osm_id, name, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id, 'name': name, 'type': 'allotment'}
        })

    return Response({'type': 'FeatureCollection', 'features': features})


@api_view(['GET'])
def meadows(request):
    """Get meadows as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT osm_id, ST_AsGeoJSON(geom) as geojson
            FROM osm_meadow
            LIMIT 5000
        """)
        rows = cursor.fetchall()

    features = []
    for osm_id, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id, 'type': 'meadow'}
        })

    return Response({'type': 'FeatureCollection', 'features': features})


@api_view(['GET'])
def farmland(request):
    """Get farmland as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT osm_id, ST_AsGeoJSON(geom) as geojson
            FROM osm_farmland
            LIMIT 5000
        """)
        rows = cursor.fetchall()

    features = []
    for osm_id, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id, 'type': 'farmland'}
        })

    return Response({'type': 'FeatureCollection', 'features': features})


@api_view(['GET'])
def parks(request):
    """Get parks as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT osm_id, name, ST_AsGeoJSON(geom) as geojson
            FROM osm_parks
            LIMIT 5000
        """)
        rows = cursor.fetchall()

    features = []
    for osm_id, name, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id, 'name': name, 'type': 'park'}
        })

    return Response({'type': 'FeatureCollection', 'features': features})


@api_view(['GET'])
def scrub(request):
    """Get scrub/bushes as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT osm_id, ST_AsGeoJSON(geom) as geojson
            FROM osm_scrub
            LIMIT 10000
        """)
        rows = cursor.fetchall()

    features = []
    for osm_id, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id, 'type': 'scrub'}
        })

    return Response({'type': 'FeatureCollection', 'features': features})


@api_view(['GET'])
def railway(request):
    """Get railway lines as GeoJSON for map layer."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT osm_id, name, ST_AsGeoJSON(geom) as geojson
            FROM osm_railway
            LIMIT 5000
        """)
        rows = cursor.fetchall()

    features = []
    for osm_id, name, geojson in rows:
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson),
            'properties': {'osm_id': osm_id, 'name': name, 'type': 'railway'}
        })

    return Response({'type': 'FeatureCollection', 'features': features})


# =============================================================================
# SAMPLE SWITCHING (Test datasets)
# =============================================================================

VALID_SAMPLES = {
    'mala': {'n': 100, 'file': 'baza_mala.json'},
    'srednia': {'n': 500, 'file': 'baza_srednia.json'},
    'duza': {'n': 1500, 'file': 'baza_duza.json'},
    'pelna': {'n': 3500, 'file': 'baza_ogromna.json'},
}


@api_view(['GET'])
def samples_current(request):
    """
    Get current sample info.

    GET /api/analytics/samples/current/
    """
    from sightings.models import Sighting

    count = Sighting.objects.filter(status='verified').count()

    # Determine which sample based on count
    current_sample = 'unknown'
    for sample_id, info in VALID_SAMPLES.items():
        if abs(count - info['n']) < 50:  # tolerance
            current_sample = sample_id
            break

    return Response({
        'current_sample': current_sample,
        'sighting_count': count,
        'available_samples': list(VALID_SAMPLES.keys()),
    })


@api_view(['POST'])
@permission_classes([IsBearerAuthenticated])
def samples_switch(request):
    """
    Switch to a different sample database.

    POST /api/analytics/samples/switch/
    Body: {"sample": "srednia"}
    """
    from .tasks import switch_sample_task

    sample = request.data.get('sample')

    if sample not in VALID_SAMPLES:
        return Response({
            'error': f'Invalid sample. Valid: {list(VALID_SAMPLES.keys())}'
        }, status=400)

    # Check if already switching
    progress = cache.get('sample_switch_progress', {})
    if progress.get('running'):
        return Response({
            'status': 'already_running',
            'message': 'Przełączanie już trwa',
        }, status=409)

    # Start task
    task = switch_sample_task.delay(sample)

    cache.set('sample_switch_progress', {
        'running': True,
        'task_id': task.id,
        'sample': sample,
        'current': 0,
        'total': 4,
        'step': 'starting',
        'message': 'Uruchamianie...',
    }, timeout=600)

    return Response({
        'task_id': task.id,
        'sample': sample,
        'expected_n': VALID_SAMPLES[sample]['n'],
    })


@api_view(['GET'])
def sample_task_progress(request, task_id):
    """
    Get sample switch task progress.

    GET /api/analytics/tasks/{task_id}/status/
    """
    progress = cache.get('sample_switch_progress', {})

    if progress.get('task_id') != task_id:
        # Check Celery result
        try:
            result = TaskResult.objects.get(task_id=task_id)
            return Response({
                'status': result.status,
                'result': result.result,
            })
        except TaskResult.DoesNotExist:
            return Response({
                'status': 'PENDING',
                'message': 'Task not found',
            })

    return Response({
        'status': 'PROGRESS' if progress.get('running') else 'SUCCESS',
        'current': progress.get('current', 0),
        'total': progress.get('total', 4),
        'percent': int(progress.get('current', 0) / progress.get('total', 4) * 100),
        'step': progress.get('step', ''),
        'message': progress.get('message', ''),
        'error': progress.get('error'),
    })


@api_view(['POST'])
def calculate_voronoi_features(request):
    """
    Calculate environmental features for Voronoi cells.

    POST /api/analytics/voronoi/features/

    This must be called after 01_generate_voronoi.R creates the cells.
    It populates: distance_to_forest, distance_to_water, forest_cover,
                  building_density, road_density
    """
    import logging
    logger = logging.getLogger(__name__)

    results = {
        'distance_to_forest': {'updated': 0, 'error': None},
        'distance_to_water': {'updated': 0, 'error': None},
        'forest_cover': {'updated': 0, 'error': None},
        'building_density': {'updated': 0, 'error': None},
        'road_density': {'updated': 0, 'error': None},
    }

    with connection.cursor() as cursor:
        # Check voronoi cells exist
        cursor.execute("SELECT COUNT(*) FROM sightings_gridcell_voronoi")
        cell_count = cursor.fetchone()[0]
        if cell_count == 0:
            return Response({
                'status': 'error',
                'message': 'No Voronoi cells found. Run 01_generate_voronoi.R first.'
            }, status=400)

        logger.info(f"Calculating features for {cell_count} Voronoi cells...")

        # 1. Distance to forest (edge-to-edge, in meters)
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
                results['distance_to_forest']['updated'] = cursor.rowcount
                logger.info(f"  distance_to_forest: {cursor.rowcount} updated")
        except Exception as e:
            results['distance_to_forest']['error'] = str(e)
            logger.error(f"  distance_to_forest ERROR: {e}")

        # 2. Distance to water (edge-to-edge, in meters)
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
                results['distance_to_water']['updated'] = cursor.rowcount
                logger.info(f"  distance_to_water: {cursor.rowcount} updated")
        except Exception as e:
            results['distance_to_water']['error'] = str(e)
            logger.error(f"  distance_to_water ERROR: {e}")

        # 3. Forest cover (% of cell covered by forest)
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
            results['forest_cover']['updated'] = cursor.rowcount
            logger.info(f"  forest_cover: {cursor.rowcount} updated")
        except Exception as e:
            results['forest_cover']['error'] = str(e)
            logger.error(f"  forest_cover ERROR: {e}")

        # 4. Building density (% of cell covered by buildings)
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
            results['building_density']['updated'] = cursor.rowcount
            logger.info(f"  building_density: {cursor.rowcount} updated")
        except Exception as e:
            results['building_density']['error'] = str(e)
            logger.error(f"  building_density ERROR: {e}")

        # 5. Road density (km of roads per km2 of cell)
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
            results['road_density']['updated'] = cursor.rowcount
            logger.info(f"  road_density: {cursor.rowcount} updated")
        except Exception as e:
            results['road_density']['error'] = str(e)
            logger.error(f"  road_density ERROR: {e}")

        # Update timestamp
        cursor.execute("UPDATE sightings_gridcell_voronoi SET updated_at = NOW()")

    # Clear cache
    cache.clear()

    # Check for any errors
    errors = [f for f, v in results.items() if v['error']]

    return Response({
        'status': 'success' if not errors else 'partial',
        'cells': cell_count,
        'results': results,
        'errors': errors
    })


# =============================================================================
# BAYESIAN LAYER ENDPOINTS (MASTER_SPEC v2.3)
# =============================================================================

@api_view(['GET'])
def bayesian_results(request):
    """
    Get Bayesian SSM results as GeoJSON.

    GET /api/analytics/bayesian/
    Query params:
    - grid_type: 'square' or 'voronoi' (default: 'voronoi')
    - run_id: filter by specific run (optional)
    - min_prob: filter by prob_above_threshold >= value (optional)

    Returns posterior mean intensity with credible intervals.
    """
    grid_type = request.GET.get('grid_type', 'voronoi')
    run_id = request.GET.get('run_id')
    min_prob = request.GET.get('min_prob')

    try:
        grid_table = validate_grid_type(grid_type)
    except ValueError:
        return Response({'error': f'Invalid grid_type: {grid_type}'}, status=400)

    query = f"""
        SELECT
            br.cell_id,
            br.intensity_mean,
            br.intensity_median,
            br.ci_lower_95,
            br.ci_upper_95,
            br.prob_above_threshold,
            br.r_hat,
            br.ess_bulk,
            br.computed_at,
            ST_AsGeoJSON(gc.geometry) as geojson
        FROM analytics_bayesian_result br
        JOIN {grid_table} gc ON gc.id = br.cell_id
        WHERE br.grid_type = %s
    """
    params = [grid_type]

    if run_id:
        query += " AND br.execution_id IN (SELECT id FROM analytics_analyticsrun WHERE task_id = %s)"
        params.append(run_id)

    if min_prob:
        query += " AND br.prob_above_threshold >= %s"
        params.append(float(min_prob))

    query += " ORDER BY br.prob_above_threshold DESC LIMIT 5000"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    features = []
    for row in rows:
        cell_id, intensity_mean, intensity_median, ci_lower, ci_upper, prob, r_hat, ess, computed_at, geojson = row
        features.append({
            'type': 'Feature',
            'geometry': json.loads(geojson) if geojson else None,
            'properties': {
                'cell_id': cell_id,
                'intensity_mean': float(intensity_mean) if intensity_mean else 0,
                'intensity_median': float(intensity_median) if intensity_median else 0,
                'ci_lower_95': float(ci_lower) if ci_lower else 0,
                'ci_upper_95': float(ci_upper) if ci_upper else 0,
                'prob_above_threshold': float(prob) if prob else 0,
                'r_hat': float(r_hat) if r_hat else None,
                'ess_bulk': float(ess) if ess else None,
                'converged': float(r_hat) < 1.01 if r_hat else None,
            }
        })

    return Response({
        'type': 'FeatureCollection',
        'features': features,
        'metadata': {
            'count': len(features),
            'grid_type': grid_type,
        }
    })


@api_view(['GET'])
def prior_configs(request):
    """
    Get active prior configurations.

    GET /api/analytics/priors/
    Query params:
    - active_only: if 'true', only return active configs (default: true)
    - parameter: filter by parameter_name (optional)

    Returns prior hyperparameters for Bayesian modeling.
    """
    from .models_bayesian import PriorConfig

    active_only = request.GET.get('active_only', 'true').lower() == 'true'
    parameter = request.GET.get('parameter')

    queryset = PriorConfig.objects.all()

    if active_only:
        queryset = queryset.filter(is_active=True)

    if parameter:
        queryset = queryset.filter(parameter_name=parameter)

    queryset = queryset.order_by('-created_at')[:100]

    configs = []
    for pc in queryset:
        configs.append({
            'id': str(pc.id),
            'model_version': pc.model_version,
            'parameter_name': pc.parameter_name,
            'dist_type': pc.dist_type,
            'alpha_hyper': float(pc.alpha_hyper),
            'beta_hyper': float(pc.beta_hyper),
            'source': {
                'h_rel': float(pc.source_h_rel) if pc.source_h_rel else None,
                'ari': float(pc.source_ari) if pc.source_ari else None,
                'bandwidth': float(pc.source_bandwidth) if pc.source_bandwidth else None,
            },
            'is_active': pc.is_active,
            'created_at': pc.created_at.isoformat(),
        })

    return Response({
        'priors': configs,
        'count': len(configs),
    })


# =============================================================================
# PRESET PROFILES ENDPOINTS
# =============================================================================

@api_view(['GET'])
def presets_list(request):
    """
    Get available preset profiles.

    GET /api/analytics/presets/

    Returns list of preset profiles with their parameters.
    """
    from .models_config import PRESET_PROFILES

    presets = []
    for key, preset in PRESET_PROFILES.items():
        presets.append({
            'id': key,
            'name': preset.get('name', key),
            'description': preset.get('description', ''),
            'parameters': {
                'bayesian_kappa': preset.get('bayesian_kappa'),
                'persistence_rho_mean': preset.get('persistence_rho_mean'),
                'diffusion_delta_mean': preset.get('diffusion_delta_mean'),
                'mcmc_iterations': preset.get('mcmc_iterations'),
                'mcmc_warmup': preset.get('mcmc_warmup'),
                'mcmc_chains': preset.get('mcmc_chains'),
            }
        })

    return Response({
        'presets': presets,
        'count': len(presets),
    })


@api_view(['POST'])
@permission_classes([IsBearerAuthenticated])
def apply_preset(request):
    """
    Apply a preset profile to create/update configuration.

    POST /api/analytics/config/apply-preset/
    Body: {"preset": "quick_preview", "activate": true}

    Creates a new ParameterConfiguration from the preset.
    If activate=true, makes it the active configuration.
    """
    from .models_config import ParameterConfiguration, PRESET_PROFILES

    preset_name = request.data.get('preset')
    activate = request.data.get('activate', True)

    if not preset_name:
        return Response(
            {'error': 'Missing "preset" field'},
            status=400
        )

    if preset_name not in PRESET_PROFILES:
        return Response(
            {'error': f'Unknown preset: {preset_name}', 'valid_presets': list(PRESET_PROFILES.keys())},
            status=400
        )

    try:
        from .models_config import PRESET_PROFILES
        preset = PRESET_PROFILES[preset_name]
        
        # Check if config with this name already exists
        existing = ParameterConfiguration.objects.filter(
            name__iexact=preset.get('name', preset_name)
        ).first()
        
        if existing:
            # Update existing config and activate it
            existing.apply_preset(preset_name)
            existing.is_active = activate
            existing.full_clean()
            existing.save()
            config = existing
            action = 'Updated'
        else:
            # Create new config
            config = ParameterConfiguration.create_from_preset(preset_name, activate=activate)
            action = 'Created'

        return Response({
            'status': 'success',
            'message': f'{action} configuration from preset: {preset_name}',
            'config': {
                'id': config.pk,
                'name': config.name,
                'description': config.description,
                'is_active': config.is_active,
                'mcmc_iterations': config.mcmc_iterations,
                'mcmc_chains': config.mcmc_chains,
            }
        })

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=500
        )


@api_view(['GET'])
def active_config(request):
    """
    Get the currently active parameter configuration.

    GET /api/analytics/config/active/

    Returns the active configuration or defaults if none set.
    """
    from .models_config import ParameterConfiguration

    config = ParameterConfiguration.get_active()

    if config:
        return Response({
            'has_active_config': True,
            'config': {
                'id': config.pk,
                'name': config.name,
                'description': config.description,
                'bayesian_kappa': float(config.bayesian_kappa),
                'persistence_rho_mean': float(config.persistence_rho_mean),
                'diffusion_delta_mean': float(config.diffusion_delta_mean),
                'mcmc_iterations': config.mcmc_iterations,
                'mcmc_warmup': config.mcmc_warmup,
                'mcmc_chains': config.mcmc_chains,
                'bayesian_enabled': config.bayesian_enabled,
                'weights': {
                    'rf': float(config.weight_rf),
                    'gwr': float(config.weight_gwr),
                    'eta': float(config.weight_eta),
                },
                'updated_at': config.updated_at.isoformat(),
            }
        })
    else:
        defaults = ParameterConfiguration.get_active_or_defaults()
        return Response({
            'has_active_config': False,
            'config': defaults,
            'message': 'Using default configuration (no active config in database)',
        })


# =============================================================================
# BAYESIAN PIPELINE EXECUTION (FAZA 3)
# =============================================================================

@api_view(['POST'])
@permission_classes([IsBearerAuthenticated])
def bayesian_run(request):
    """
    Run the Bayesian pipeline.

    POST /api/analytics/bayesian/run/
    Body: {
        "h_rel": 0.5,        # relative entropy (0-1)
        "ari": 0.7,          # adjusted Rand index (0-1)
        "bandwidth": 400.0   # GWR bandwidth in meters
    }

    Triggers:
    1. elicit_priors (OP-B01)
    2. compute_bayesian_ssm (OP-B02)
    3. generate_trajectories (OP-B03)

    Returns: { "task_id": "...", "status": "queued" }
    """
    from .tasks_bayesian import run_bayesian_pipeline
    from .models_config import ParameterConfiguration
    import uuid

    # Get parameters from request or use defaults
    try:
        h_rel = float(request.data.get('h_rel', 0.5))
        ari = float(request.data.get('ari', 0.7))
        bandwidth = float(request.data.get('bandwidth', 400.0))
    except (TypeError, ValueError):
        return Response({'error': 'h_rel, ari and bandwidth must be numeric'}, status=400)

    # Validate inputs
    errors = []
    if not (0 < h_rel <= 1):
        errors.append('h_rel must be in (0, 1]')
    if not (0 <= ari <= 1):
        errors.append('ari must be in [0, 1]')
    if bandwidth <= 0:
        errors.append('bandwidth must be > 0')

    if errors:
        return Response({'error': '; '.join(errors)}, status=400)

    # Atomic lock — prevents concurrent 4-hour pipeline runs exhausting workers.
    # cache.add() is atomic: returns True only when the key did NOT exist.
    BAYESIAN_LOCK_KEY = 'bayesian_pipeline_lock'
    BAYESIAN_LOCK_TIMEOUT = 14400  # 4 hours max (matches task time_limit)

    if not cache.add(BAYESIAN_LOCK_KEY, 'running', BAYESIAN_LOCK_TIMEOUT):
        return Response(
            {
                'status': 'already_running',
                'message': 'Bayesian pipeline already in progress. Check /api/analytics/bayesian/status/',
            },
            status=409,
        )

    # Get active config for MCMC settings
    config = ParameterConfiguration.get_active_or_defaults()

    # Trigger the pipeline
    try:
        kappa = float(config.get('kappa', 10.0))
        grid_type = request.data.get('grid_type', 'voronoi')

        task = run_bayesian_pipeline.delay(
            h_rel=h_rel,
            ari=ari,
            bandwidth=bandwidth,
            grid_type=grid_type,
            kappa=kappa,
        )

        # Use task ID as run_id
        run_id = task.id

        # Store task info in cache for polling
        from django.core.cache import cache
        cache.set(f'bayesian_task:{run_id}', {
            'task_id': task.id,
            'status': 'queued',
            'run_id': run_id,
        }, timeout=86400)

        return Response({
            'status': 'queued',
            'task_id': task.id,
            'run_id': run_id,
            'message': 'Bayesian pipeline started',
            'config': {
                'h_rel': h_rel,
                'ari': ari,
                'bandwidth': bandwidth,
                'kappa': kappa,
                'grid_type': grid_type,
            }
        })

    except Exception as e:
        # Dispatch failed — release the lock so a retry is possible.
        cache.delete(BAYESIAN_LOCK_KEY)
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def bayesian_diagnostics(request):
    """
    Get MCMC diagnostics from the most recent Bayesian run.

    GET /api/analytics/bayesian/diagnostics/
    Query params:
    - run_id: specific run to get diagnostics for (optional)

    Returns:
    - r_hat_max: maximum R-hat across all parameters
    - r_hat_mean: mean R-hat
    - ess_min: minimum effective sample size
    - ess_mean: mean effective sample size
    - divergences: number of divergent transitions
    - convergence_ok: boolean indicating if all diagnostics pass
    """
    run_id = request.GET.get('run_id')

    # Query latest diagnostics from BayesianResult
    query = """
        SELECT
            MAX(r_hat) as r_hat_max,
            AVG(r_hat) as r_hat_mean,
            MIN(ess_bulk) as ess_min,
            AVG(ess_bulk) as ess_mean,
            COUNT(*) as n_cells,
            COUNT(CASE WHEN r_hat > 1.01 THEN 1 END) as n_bad_rhat,
            COUNT(CASE WHEN ess_bulk < 400 THEN 1 END) as n_low_ess,
            MAX(computed_at) as last_computed
        FROM analytics_bayesian_result
    """
    params = []

    if run_id:
        query += " WHERE execution_id IN (SELECT id FROM analytics_analyticsrun WHERE task_id = %s)"
        params.append(run_id)

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()

    if not row or row[4] == 0:  # n_cells is 0
        return Response({
            'has_diagnostics': False,
            'message': 'No Bayesian results found. Run the pipeline first.',
        })

    r_hat_max, r_hat_mean, ess_min, ess_mean, n_cells, n_bad_rhat, n_low_ess, last_computed = row

    # Check convergence criteria
    convergence_ok = (
        (r_hat_max is None or float(r_hat_max) <= 1.01) and
        (ess_min is None or float(ess_min) >= 400)
    )

    return Response({
        'has_diagnostics': True,
        'diagnostics': {
            'r_hat_max': float(r_hat_max) if r_hat_max else None,
            'r_hat_mean': float(r_hat_mean) if r_hat_mean else None,
            'ess_min': float(ess_min) if ess_min else None,
            'ess_mean': float(ess_mean) if ess_mean else None,
            'n_cells': n_cells,
            'n_bad_rhat': n_bad_rhat,
            'n_low_ess': n_low_ess,
            'convergence_ok': convergence_ok,
            'last_computed': last_computed.isoformat() if last_computed else None,
        },
        'thresholds': {
            'r_hat_threshold': 1.01,
            'ess_threshold': 400,
        }
    })


# =============================================================================
# COMBINED RESULTS FOR RESULTS TABLE (FAZA 5)
# =============================================================================

@api_view(['GET'])
def combined_results(request):
    """
    Get combined model results for ResultsTable.

    GET /api/analytics/results/combined/
    Query params:
    - grid_type: 'square' or 'voronoi' (default: 'voronoi')
    - limit: max rows (default: 100)
    - min_risk: filter by ensemble >= value (optional)

    Returns aggregated predictions from RF, GWR, ETA, Bayesian.
    """
    grid_type = request.GET.get('grid_type', 'voronoi')
    limit = validate_limit(request.GET.get('limit', 100))
    min_risk = request.GET.get('min_risk')

    try:
        grid_table = validate_grid_type(grid_type)
    except ValueError:
        return Response({'error': f'Invalid grid_type: {grid_type}'}, status=400)

    # Query grid cells directly (they have ensemble_risk, gwr_score, area_rank_score)
    # spatial_risk only exists in voronoi table (SAR/SEM output)
    # RF comes from analytics_modelprediction, Bayesian from analytics_bayesian_result
    gwr_select = "COALESCE(gc.spatial_risk, gc.gwr_score, 0)" if grid_type == "voronoi" else "gc.gwr_score"
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

    query += f" ORDER BY gc.ensemble_risk DESC LIMIT {limit}"  # limit already validated by validate_limit

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    results = []
    high_risk_count = 0
    for row in rows:
        cell_id, rf, gwr, eta, bayesian, ensemble, prob_above, r_hat, ess = row
        result = {
            'cell_id': cell_id,
            'rf': float(rf) if rf else None,
            'gwr': float(gwr) if gwr else None,
            'eta': float(eta) if eta else None,
            'bayesian': float(bayesian) if bayesian else None,
            'ensemble': float(ensemble) if ensemble else None,
            'prob_above_threshold': float(prob_above) if prob_above else None,
            'r_hat': float(r_hat) if r_hat else None,
            'ess': float(ess) if ess else None,
        }
        results.append(result)
        if ensemble and float(ensemble) > 0.7:
            high_risk_count += 1

    return Response({
        'results': results,
        'count': len(results),
        'high_risk_count': high_risk_count,
        'grid_type': grid_type,
    })


@api_view(['GET'])
def export_results_csv(request):
    """
    Export combined results as CSV.

    GET /api/analytics/results/export/
    Query params: same as combined_results
    """
    import csv
    from django.http import HttpResponse

    grid_type = request.GET.get('grid_type', 'voronoi')

    try:
        grid_table = validate_grid_type(grid_type)
    except ValueError:
        return HttpResponse(f'Invalid grid_type: {grid_type}', status=400)
    # spatial_risk only exists in voronoi table (SAR/SEM output)
    gwr_select = "COALESCE(gc.spatial_risk, gc.gwr_score, 0)" if grid_type == "voronoi" else "gc.gwr_score"
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

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="risk_results_{grid_type}.csv"'

    writer = csv.writer(response)
    writer.writerow(['cell_id', 'rf', 'gwr', 'eta', 'bayesian', 'ensemble', 'prob_above_threshold', 'r_hat', 'ess'])

    for row in rows:
        writer.writerow(row)

    return response


# =============================================================================
# MODE ROUTER (FAST/PUB/BAYES pipeline separation)
# =============================================================================

@api_view(['POST'])
@permission_classes([IsBearerAuthenticated])
def run_mode_pipeline(request):
    """
    Run analytics pipeline with specified mode.

    POST /api/analytics/pipeline/
    Body: {
        "mode": "FAST" | "PUB" | "BAYES",
        "async": true | false  (default: false)
    }

    Modes:
    - FAST: Voronoi + RF + GWR heuristic + simple ETA (~1s)
    - PUB:  Square + real GWR (R) + full ETA (TODO)
    - BAYES: Square + MCMC + CAR spatial (TODO)

    Returns:
    - sync (async=false): Full result with debug summary
    - async (async=true): Task ID for polling
    """
    from .mode_router import run_pipeline, MODE_CONFIG

    mode = request.data.get('mode', 'FAST').upper()
    run_async = request.data.get('async', False)

    # Validate mode
    if mode not in MODE_CONFIG:
        return Response({
            'status': 'error',
            'message': f'Invalid mode: {mode}',
            'valid_modes': list(MODE_CONFIG.keys()),
        }, status=400)

    config = MODE_CONFIG[mode]

    if run_async:
        # Async execution via Celery
        task = run_pipeline.delay(mode=mode)

        cache.set(f'pipeline_task:{task.id}', {
            'task_id': task.id,
            'mode': mode,
            'status': 'queued',
        }, timeout=3600)

        return Response({
            'status': 'queued',
            'task_id': task.id,
            'mode': mode,
            'config': config,
            'message': f'{mode} pipeline started (async)',
        })
    else:
        # Sync execution (blocking)
        try:
            result = run_pipeline(mode=mode)
            return Response({
                'status': result.get('status', 'unknown'),
                'mode': mode,
                'config': config,
                'result': result,
            })
        except Exception as e:
            return Response({
                'status': 'error',
                'mode': mode,
                'message': str(e),
            }, status=500)


@api_view(['GET'])
def pipeline_status(request, task_id):
    """
    Get pipeline task status.

    GET /api/analytics/pipeline/{task_id}/status/
    """
    from django_celery_results.models import TaskResult

    # Check cache first
    cached = cache.get(f'pipeline_task:{task_id}')
    if cached:
        # Check if task is finished
        try:
            result = TaskResult.objects.get(task_id=task_id)
            if result.status == 'SUCCESS':
                return Response({
                    'status': 'success',
                    'task_id': task_id,
                    'mode': cached.get('mode'),
                    'result': result.result,
                })
            elif result.status == 'FAILURE':
                return Response({
                    'status': 'error',
                    'task_id': task_id,
                    'mode': cached.get('mode'),
                    'error': str(result.result),
                })
            else:
                return Response({
                    'status': 'running',
                    'task_id': task_id,
                    'mode': cached.get('mode'),
                })
        except TaskResult.DoesNotExist:
            return Response({
                'status': 'running',
                'task_id': task_id,
                'mode': cached.get('mode'),
            })

    return Response({
        'status': 'not_found',
        'task_id': task_id,
        'message': 'Task not found',
    }, status=404)


@api_view(['GET'])
def pipeline_modes(request):
    """
    Get available pipeline modes and their configurations.

    GET /api/analytics/pipeline/modes/
    """
    from .mode_router import MODE_CONFIG

    return Response({
        'modes': MODE_CONFIG,
        'default': 'FAST',
    })


# =============================================================================
# ETA and Spatial Model Results (spatialWarsaw compliance)
# =============================================================================

@api_view(['GET'])
def eta_current(request):
    """
    Get current ETA (Entropy Tessellation for Agglomeration) statistics.

    GET /api/analytics/eta/current/

    Returns global ETA metrics calculated from Voronoi tessellation.
    Source: spatialWarsaw::ETA() implementation
    """
    with connection.cursor() as cursor:
        # Calculate ETA from area_proportion (ri = Ai / sum(Aj))
        # H = -sum(ri * ln(ri)), H_max = ln(n), H_rel = H / H_max
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

        # Also get per-cell area_rank_score statistics
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
        return Response({
            'error': 'No Voronoi tessellation data available',
            'source': 'spatialWarsaw::ETA()',
        }, status=404)

    n_tiles, s_ent, h_max, h_rel = row
    avg_area_rank, min_area_rank, max_area_rank, std_area_rank, avg_area_prop = stats_row or (None,)*5

    # Interpretation based on Kopczewska's documentation
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

    return Response({
        'h_rel': round(float(h_rel), 4) if h_rel else None,
        's_ent': round(float(s_ent), 4) if s_ent else None,
        'h_max': round(float(h_max), 4) if h_max else None,
        'n_tiles': n_tiles,
        'interpretation': interpretation,
        'cell_stats': {
            'avg_area_rank_score': round(float(avg_area_rank), 4) if avg_area_rank else None,
            'min_area_rank_score': round(float(min_area_rank), 4) if min_area_rank else None,
            'max_area_rank_score': round(float(max_area_rank), 4) if max_area_rank else None,
            'std_area_rank_score': round(float(std_area_rank), 4) if std_area_rank else None,
            'avg_area_proportion': round(float(avg_area_prop), 6) if avg_area_prop else None,
        },
        'source': 'spatialWarsaw::ETA() — 100% zgodne',
        'reference': 'spatialWarsaw::ETA() via tessellation',
    })


@api_view(['GET'])
def spatial_current(request):
    """
    Get current spatial regression model results.

    GET /api/analytics/spatial/current/

    Returns the latest SAR/SEM model estimation results.
    Source: spatialWarsaw + spatialreg (lagsarlm/errorsarlm)
    """
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
        return Response({
            'error': 'No spatial model results available. Run NEW_02_spatial_models.R first.',
            'source': 'spatialreg::lagsarlm/errorsarlm',
        }, status=404)

    id_, computed_at, model_type, n_cells, rho, lambda_, aic, formula = row

    # Model interpretation
    if model_type == 'SAR':
        description = "Spatial Autoregressive Model (lagsarlm): y = ρWy + Xβ + ε"
        spatial_param = {'name': 'rho (ρ)', 'value': round(float(rho), 4) if rho else None}
    elif model_type == 'SEM':
        description = "Spatial Error Model (errorsarlm): y = Xβ + u, u = λWu + ε"
        spatial_param = {'name': 'lambda (λ)', 'value': round(float(lambda_), 4) if lambda_ else None}
    else:
        description = f"{model_type} model"
        spatial_param = {'name': 'N/A', 'value': None}

    return Response({
        'model_type': model_type,
        'description': description,
        'n_cells': n_cells,
        'spatial_param': spatial_param,
        'rho': round(float(rho), 4) if rho else None,
        'lambda': round(float(lambda_), 4) if lambda_ else None,
        'aic': round(float(aic), 2) if aic else None,
        'formula': formula,
        'computed_at': computed_at.isoformat() if computed_at else None,
        'source': 'spatialreg::lagsarlm/errorsarlm',
        'reference': 'NEW_02_spatial_models.R',
    })


# =============================================================================
# W MATRIX VISUALIZATION
# =============================================================================

@api_view(['GET'])
def w_matrix_edges(request):
    """
    Get W matrix edges as GeoJSON for visualization.
    
    GET /api/analytics/w-matrix/edges/
    
    Returns LineString features representing spatial neighbor connections.
    Each edge connects two cell centroids that are neighbors in the W matrix.
    
    The file is generated by r_scripts/research/export_w_edges.R during pipeline run.
    """
    import os
    
    geojson_path = '/r_data/w_matrix_edges.geojson'
    
    if not os.path.exists(geojson_path):
        return Response({
            'error': 'W matrix edges not available. Run the research pipeline first.',
            'path': geojson_path,
        }, status=404)
    
    # Read and return the GeoJSON file
    with open(geojson_path, 'r') as f:
        geojson_data = json.load(f)
    
    # Add metadata
    n_edges = len(geojson_data.get('features', []))
    
    return Response({
        'type': 'FeatureCollection',
        'metadata': {
            'n_edges': n_edges,
            'description': 'Spatial neighbor connections (W matrix edges)',
            'source': 'research_W.rds via export_w_edges.R',
        },
        'features': geojson_data.get('features', []),
    })
