"""
API views for Research Pipeline.

Endpoints:
    /api/research/configs/              GET, POST
    /api/research/configs/{id}/         GET, PUT
    /api/research/configs/{id}/activate/ POST
    /api/research/run/                  POST
    /api/research/runs/                 GET
    /api/research/runs/{id}/            GET
    /api/research/runs/{id}/steps/      GET
    /api/research/runs/{id}/diagnostics/ GET
    /api/research/status/               GET
"""

import logging

from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsBearerAuthenticated
from .sql_injection_patch import validate_geometry_type
from .models_research import (
    ResearchConfig,
    ResearchRun,
    ResearchStepLog,
    ResearchDiagnostics,
    ALL_PREDICTORS,
)

logger = logging.getLogger(__name__)


# =============================================================================
# SERIALIZERS (dict-based, matching existing project style)
# =============================================================================

def _serialize_config(c: ResearchConfig) -> dict:
    return {
        'id': c.pk,
        'name': c.name,
        'is_active': c.is_active,
        'geometry_type': c.geometry_type,
        'population_method': c.population_method,
        'y_formula': c.y_formula,
        'w_method': c.w_method,
        'k_range_min': c.k_range_min,
        'k_range_max': c.k_range_max,
        'model_type': c.model_type,
        'active_predictors': c.active_predictors,
        'run_moran': c.run_moran,
        'run_lm_tests': c.run_lm_tests,
        'run_lisa': c.run_lisa,
        'run_eta': c.run_eta,
        'vif_threshold': c.vif_threshold,
        'alpha': c.alpha,
        'seed': c.seed,
        'date_from': c.date_from.isoformat() if c.date_from else None,
        'date_to': c.date_to.isoformat() if c.date_to else None,
        # Regime model fields
        'use_regime_model': c.use_regime_model,
        'regime_type': c.regime_type,
        'regime_threshold': c.regime_threshold,
        'regime_threshold_urban': c.regime_threshold_urban,
        'created_at': c.created_at.isoformat() if c.created_at else None,
        'updated_at': c.updated_at.isoformat() if c.updated_at else None,
    }


def _serialize_run(r: ResearchRun) -> dict:
    return {
        'id': str(r.id),
        'config_name': r.config.name if r.config else None,
        'config_id': r.config_id,
        'status': r.status,
        'n_sightings': r.n_sightings,
        'n_cells': r.n_cells,
        'started_at': r.started_at.isoformat() if r.started_at else None,
        'finished_at': r.finished_at.isoformat() if r.finished_at else None,
        'error_message': r.error_message or None,
    }


def _serialize_run_detail(r: ResearchRun) -> dict:
    data = _serialize_run(r)
    data['config_snapshot'] = r.config_snapshot
    return data


def _serialize_step(s: ResearchStepLog) -> dict:
    return {
        'step_order': s.step_order,
        'step_name': s.step_name,
        'step_type': s.step_type,
        'status': s.status,
        'exit_code': s.exit_code,
        'duration_seconds': s.duration_seconds,
        'started_at': s.started_at.isoformat() if s.started_at else None,
        'finished_at': s.finished_at.isoformat() if s.finished_at else None,
        'stdout': s.stdout[:500] if s.stdout else None,
        'stderr': s.stderr[:500] if s.stderr else None,
        'output_stats': s.output_stats,
        'errors': s.errors,
        'warnings': s.warnings,
    }


def _serialize_diagnostics(d: ResearchDiagnostics) -> dict:
    return {
        'moran': {
            'i': d.moran_i,
            'expected': d.moran_expected,
            'variance': d.moran_variance,
            'z': d.moran_z,
            'p': d.moran_p,
        },
        'lm_tests': {
            'lm_lag': {'stat': d.lm_lag_stat, 'p': d.lm_lag_p},
            'lm_error': {'stat': d.lm_error_stat, 'p': d.lm_error_p},
            'rlm_lag': {'stat': d.rlm_lag_stat, 'p': d.rlm_lag_p},
            'rlm_error': {'stat': d.rlm_error_stat, 'p': d.rlm_error_p},
        },
        'model': {
            'selected': d.model_selected,
            'aic': d.aic,
            'log_likelihood': d.log_likelihood,
            'r_squared': d.r_squared,
            'rho': d.rho,
            'lambda': d.lambda_param,
            'coefficients': d.coefficients,
        },
        'lisa': {
            'hh': d.lisa_hh_count,
            'll': d.lisa_ll_count,
            'hl': d.lisa_hl_count,
            'lh': d.lisa_lh_count,
            'ns': d.lisa_ns_count,
        },
        'vif': {
            'results': d.vif_results,
            'dropped': d.predictors_dropped,
        },
        'eta': {
            'h_emp': d.eta_h_emp,
            'h_max': d.eta_h_max,
            'h_rel': d.eta_h_rel,
        },
        'w_metrics': {
            'k_selected': d.k_selected,
            'mean_neighbors': d.mean_neighbors,
        },
        # Impacts (SAR/SDM only) - LeSage & Pace (2009)
        # For SAR/SDM, β coefficients need spatial multiplier correction
        'impacts': d.impacts,
    }


# =============================================================================
# CONFIG FIELDS — accepted from request body
# =============================================================================

_CONFIG_WRITABLE_FIELDS = {
    'name': str,
    'geometry_type': str,
    'population_method': str,
    'y_formula': str,
    'w_method': str,
    'k_range_min': int,
    'k_range_max': int,
    'model_type': str,
    'active_predictors': list,
    'run_moran': bool,
    'run_lm_tests': bool,
    'run_lisa': bool,
    'run_eta': bool,
    'vif_threshold': float,
    'alpha': float,
    'seed': int,
    'date_from': str,
    'date_to': str,
    # Regime model fields
    'use_regime_model': bool,
    'regime_type': str,
    'regime_threshold': float,
    'regime_threshold_urban': float,
}


def _apply_fields(config: ResearchConfig, data: dict):
    """Apply request data fields to config object."""
    for field, expected_type in _CONFIG_WRITABLE_FIELDS.items():
        if field in data:
            value = data[field]
            # Allow null for date fields
            if field in ('date_from', 'date_to') and value is None:
                setattr(config, field, None)
            elif value is not None:
                setattr(config, field, value)


# =============================================================================
# CONFIG ENDPOINTS
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsBearerAuthenticated])
def config_list(request):
    """
    GET  /api/research/configs/   — list all configs
    POST /api/research/configs/   — create new config

    Both methods require authentication: configs are internal admin state
    (active predictors, model parameters) and must not be publicly readable.
    """
    if request.method == 'GET':
        configs = ResearchConfig.objects.all().order_by('-is_active', '-updated_at')
        return Response({
            'configs': [_serialize_config(c) for c in configs],
            'available_predictors': ALL_PREDICTORS,
        })

    # POST — create (authentication already enforced by decorator above)
    data = request.data
    if not data.get('name'):
        return Response({'error': 'name is required'}, status=400)

    config = ResearchConfig()
    _apply_fields(config, data)
    try:
        config.full_clean()
        config.save()
    except Exception as e:
        return Response({'error': str(e)}, status=400)

    return Response(_serialize_config(config), status=201)


@api_view(['GET', 'PUT'])
@permission_classes([IsBearerAuthenticated])
def config_detail(request, config_id):
    """
    GET /api/research/configs/{id}/
    PUT /api/research/configs/{id}/

    Both methods require authentication: configs are internal admin state.
    """
    try:
        config = ResearchConfig.objects.get(pk=config_id)
    except ResearchConfig.DoesNotExist:
        return Response({'error': 'Config not found'}, status=404)

    if request.method == 'GET':
        return Response(_serialize_config(config))

    # PUT — update
    _apply_fields(config, request.data)
    try:
        config.full_clean()
        config.save()
    except Exception as e:
        return Response({'error': str(e)}, status=400)

    return Response(_serialize_config(config))


@api_view(['POST'])
@permission_classes([IsBearerAuthenticated])
def config_activate(request, config_id):
    """POST /api/research/configs/{id}/activate/ — set as active config."""
    try:
        config = ResearchConfig.objects.get(pk=config_id)
    except ResearchConfig.DoesNotExist:
        return Response({'error': 'Config not found'}, status=404)

    config.is_active = True
    try:
        config.full_clean()
        config.save()
    except Exception as e:
        return Response({'error': str(e)}, status=400)

    return Response({
        'status': 'activated',
        'config': _serialize_config(config),
    })


# =============================================================================
# RUN ENDPOINTS
# =============================================================================

@api_view(['POST'])
@permission_classes([IsBearerAuthenticated])
def run_pipeline(request):
    """
    POST /api/research/run/ — execute pipeline with active config.

    Runs ASYNCHRONOUSLY via Celery. Returns immediately with task_id AND run_id.
    run_id is used for WebSocket connection: ws://host/ws/research/run/<run_id>/
    Frontend should connect to WebSocket for live progress updates.
    """
    from .tasks_research import run_research_pipeline
    from django.db import connection

    config = ResearchConfig.objects.filter(is_active=True).first()
    if not config:
        return Response({
            'error': 'No active ResearchConfig. Create and activate one first.',
        }, status=400)

    logger.info(f"API: Starting ASYNC research pipeline with config '{config.name}'")

    # Count sightings for this run
    sql = "SELECT COUNT(*) FROM sightings_sighting WHERE status = 'verified'"
    params = []
    if config.date_from:
        sql += " AND date >= %s"
        params.append(config.date_from)
    if config.date_to:
        sql += " AND date <= %s"
        params.append(config.date_to)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        n_sightings = cursor.fetchone()[0]

    # Atomic: create run + dispatch task together — orphaned ResearchRun
    # records (run exists but task never dispatched) corrupt WebSocket state.
    from django.db import transaction

    with transaction.atomic():
        run = ResearchRun.objects.create(
            config=config,
            config_snapshot=_snapshot_config(config),
            status='pending',
            n_sightings=n_sightings,
        )
        task = run_research_pipeline.delay(str(run.id))

    return Response({
        'status': 'pending',
        'task_id': task.id,
        'run_id': str(run.id),  # For WebSocket connection
        'config_id': config.id,
        'config_name': config.name,
        'message': f"Pipeline started for '{config.name}'. Connect to ws://host/ws/research/run/{run.id}/ for live progress.",
    }, status=202)  # 202 Accepted


def _snapshot_config(config: ResearchConfig) -> dict:
    """Serialize config to a JSON-safe dict for reproducibility."""
    return {
        'name': config.name,
        'geometry_type': config.geometry_type,
        'population_method': config.population_method,
        'y_formula': config.y_formula,
        'w_method': config.w_method,
        'k_range_min': config.k_range_min,
        'k_range_max': config.k_range_max,
        'model_type': config.model_type,
        'active_predictors': config.active_predictors,
        'run_moran': config.run_moran,
        'run_lm_tests': config.run_lm_tests,
        'run_lisa': config.run_lisa,
        'run_eta': config.run_eta,
        'vif_threshold': config.vif_threshold,
        'alpha': config.alpha,
        'seed': config.seed,
        'date_from': config.date_from.isoformat() if config.date_from else None,
        'date_to': config.date_to.isoformat() if config.date_to else None,
    }


@api_view(['GET'])
def run_list(request):
    """GET /api/research/runs/ — list recent runs (last 20)."""
    runs = ResearchRun.objects.select_related('config').order_by('-started_at')[:20]
    return Response({
        'runs': [_serialize_run(r) for r in runs],
    })


@api_view(['DELETE'])
@permission_classes([IsBearerAuthenticated])
def run_clear_all(request):
    """DELETE /api/research/runs/clear/ — delete all run history."""
    count, _ = ResearchRun.objects.all().delete()
    return Response({
        'deleted': count,
        'message': f'Usunieto {count} uruchomien z historii',
    })


@api_view(['GET'])
def run_detail(request, run_id):
    """GET /api/research/runs/{id}/ — run details with config snapshot."""
    try:
        run = ResearchRun.objects.select_related('config').get(pk=run_id)
    except (ResearchRun.DoesNotExist, ValueError):
        return Response({'error': 'Run not found'}, status=404)

    return Response(_serialize_run_detail(run))


@api_view(['GET'])
@permission_classes([IsBearerAuthenticated])
def run_steps(request, run_id):
    """GET /api/research/runs/{id}/steps/ — step logs for a run."""
    try:
        run = ResearchRun.objects.get(pk=run_id)
    except (ResearchRun.DoesNotExist, ValueError):
        return Response({'error': 'Run not found'}, status=404)

    steps = run.steps.order_by('step_order')
    return Response({
        'run_id': str(run.id),
        'run_status': run.status,
        'steps': [_serialize_step(s) for s in steps],
    })


@api_view(['GET'])
@permission_classes([IsBearerAuthenticated])
def run_diagnostics(request, run_id):
    """GET /api/research/runs/{id}/diagnostics/ — diagnostic results."""
    try:
        run = ResearchRun.objects.get(pk=run_id)
    except (ResearchRun.DoesNotExist, ValueError):
        return Response({'error': 'Run not found'}, status=404)

    try:
        diag = run.diagnostics
    except ResearchDiagnostics.DoesNotExist:
        return Response({
            'run_id': str(run.id),
            'diagnostics': None,
            'message': 'No diagnostics available for this run',
        })

    return Response({
        'run_id': str(run.id),
        'diagnostics': _serialize_diagnostics(diag),
    })


# =============================================================================
# STATUS ENDPOINT
# =============================================================================

@api_view(['GET'])
def pipeline_status(request):
    """
    GET /api/research/status/ — current pipeline status overview.

    Returns active config, last run info, and sighting count.
    """
    active_config = ResearchConfig.objects.filter(is_active=True).first()
    last_run = ResearchRun.objects.order_by('-started_at').first()

    # Count verified sightings
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM sightings_sighting WHERE status = 'verified'")
        n_sightings = cursor.fetchone()[0]

    return Response({
        'active_config': _serialize_config(active_config) if active_config else None,
        'last_run': _serialize_run(last_run) if last_run else None,
        'n_sightings': n_sightings,
        'total_configs': ResearchConfig.objects.count(),
        'total_runs': ResearchRun.objects.count(),
        'available_predictors': ALL_PREDICTORS,
    })


# =============================================================================
# DISTRIBUTIONS ENDPOINT
# =============================================================================

# Mapping geometry_type -> table name
GEOMETRY_TABLE_MAP = {
    'grid_500': 'research_grid_500m',
    'voronoi': 'sightings_gridcell_voronoi',
}


@api_view(['GET'])
def distributions(request):
    """
    GET /api/research/distributions/ — histogram data for regime thresholds.

    Returns bucket counts for forest_cover and building_density
    from the appropriate table based on geometry_type.

    Query params:
        geometry_type (str): 'grid_500' or 'voronoi' (default 'grid_500')
        forest_threshold (float): threshold for forest regime (default 0.3)
        building_threshold (float): threshold for urban regime (default 0.15)
    """
    # Parse geometry_type — validated against allowlist to prevent SQL injection
    geometry_type = request.query_params.get('geometry_type', 'grid_500')
    try:
        table = validate_geometry_type(geometry_type)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=400)

    # Parse threshold params (for regime preview calculation)
    try:
        forest_threshold = float(request.query_params.get('forest_threshold', 0.3))
    except ValueError:
        forest_threshold = 0.3
    try:
        building_threshold = float(request.query_params.get('building_threshold', 0.15))
    except ValueError:
        building_threshold = 0.15

    # Clamp to valid range
    forest_threshold = max(0.0, min(1.0, forest_threshold))
    building_threshold = max(0.0, min(1.0, building_threshold))

    n_buckets = 20
    bucket_width = 1.0 / n_buckets

    with connection.cursor() as cursor:
        # Check if table exists and has data
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            n_cells = cursor.fetchone()[0] or 0
        except Exception:
            # Table doesn't exist
            return Response({
                'geometry_type': geometry_type,
                'n_cells': 0,
                'available': False,
                'message': f'Brak danych. Kliknij "Odswiez" aby wygenerowac.',
            })

        if n_cells == 0:
            return Response({
                'geometry_type': geometry_type,
                'n_cells': 0,
                'available': False,
                'message': f'Brak danych. Kliknij "Odswiez" aby wygenerowac.',
            })

        # Check if forest_cover/building_density columns have data
        cursor.execute(f"""
            SELECT
                COUNT(*) FILTER (WHERE forest_cover IS NOT NULL) as n_forest,
                COUNT(*) FILTER (WHERE building_density IS NOT NULL) as n_building
            FROM {table}
        """)
        feature_check = cursor.fetchone()
        if (feature_check[0] or 0) == 0 and (feature_check[1] or 0) == 0:
            return Response({
                'geometry_type': geometry_type,
                'n_cells': n_cells,
                'available': False,
                'message': 'Geometria istnieje, ale brak cech OSM. Kliknij "Odswiez".',
            })

        # Get last update timestamp
        try:
            cursor.execute(f"SELECT MAX(updated_at) FROM {table}")
            last_update = cursor.fetchone()[0]
        except Exception:
            last_update = None

        # Get basic stats and total count
        cursor.execute(f"""
            SELECT
                COUNT(*) as n_cells,
                MIN(COALESCE(forest_cover, 0)) as forest_min,
                MAX(COALESCE(forest_cover, 0)) as forest_max,
                AVG(COALESCE(forest_cover, 0)) as forest_mean,
                MIN(COALESCE(building_density, 0)) as building_min,
                MAX(COALESCE(building_density, 0)) as building_max,
                AVG(COALESCE(building_density, 0)) as building_mean
            FROM {table}
        """)
        row = cursor.fetchone()
        n_cells = row[0] or 0
        forest_stats = {
            'min': row[1] or 0,
            'max': row[2] or 0,
            'mean': row[3] or 0,
        }
        building_stats = {
            'min': row[4] or 0,
            'max': row[5] or 0,
            'mean': row[6] or 0,
        }

        # Get forest_cover histogram buckets
        cursor.execute(f"""
            SELECT
                width_bucket(COALESCE(forest_cover, 0), 0, 1.0001, %s) as bucket,
                COUNT(*) as count
            FROM {table}
            GROUP BY bucket
            ORDER BY bucket
        """, [n_buckets])
        forest_raw = {r[0]: r[1] for r in cursor.fetchall()}

        # Get building_density histogram buckets
        cursor.execute(f"""
            SELECT
                width_bucket(COALESCE(building_density, 0), 0, 1.0001, %s) as bucket,
                COUNT(*) as count
            FROM {table}
            GROUP BY bucket
            ORDER BY bucket
        """, [n_buckets])
        building_raw = {r[0]: r[1] for r in cursor.fetchall()}

        # Regime preview: count cells by regime classification
        # FOREST: forest_cover >= forest_threshold AND building_density < building_threshold
        # URBAN: building_density >= building_threshold AND forest_cover < forest_threshold
        # MIXED: everything else
        cursor.execute(f"""
            SELECT
                SUM(CASE
                    WHEN COALESCE(forest_cover, 0) >= %s
                         AND COALESCE(building_density, 0) < %s
                    THEN 1 ELSE 0 END) as n_forest,
                SUM(CASE
                    WHEN COALESCE(building_density, 0) >= %s
                         AND COALESCE(forest_cover, 0) < %s
                    THEN 1 ELSE 0 END) as n_urban,
                SUM(CASE
                    WHEN NOT (
                        (COALESCE(forest_cover, 0) >= %s AND COALESCE(building_density, 0) < %s)
                        OR (COALESCE(building_density, 0) >= %s AND COALESCE(forest_cover, 0) < %s)
                    )
                    THEN 1 ELSE 0 END) as n_mixed
            FROM {table}
        """, [
            forest_threshold, building_threshold,
            building_threshold, forest_threshold,
            forest_threshold, building_threshold,
            building_threshold, forest_threshold
        ])
        regime_row = cursor.fetchone()
        n_forest = regime_row[0] or 0
        n_urban = regime_row[1] or 0
        n_mixed = regime_row[2] or 0

    # Build bucket arrays
    forest_buckets = []
    building_buckets = []
    for i in range(1, n_buckets + 1):
        from_val = (i - 1) * bucket_width
        to_val = i * bucket_width
        forest_buckets.append({
            'from': round(from_val, 3),
            'to': round(to_val, 3),
            'count': forest_raw.get(i, 0),
        })
        building_buckets.append({
            'from': round(from_val, 3),
            'to': round(to_val, 3),
            'count': building_raw.get(i, 0),
        })

    return Response({
        'geometry_type': geometry_type,
        'n_cells': n_cells,
        'available': True,
        'last_update': last_update.isoformat() if last_update else None,
        'forest_cover': {
            'min': round(forest_stats['min'], 4),
            'max': round(forest_stats['max'], 4),
            'mean': round(forest_stats['mean'], 4),
            'buckets': forest_buckets,
        },
        'building_density': {
            'min': round(building_stats['min'], 4),
            'max': round(building_stats['max'], 4),
            'mean': round(building_stats['mean'], 4),
            'buckets': building_buckets,
        },
        'regime_preview': {
            'forest_threshold': forest_threshold,
            'building_threshold': building_threshold,
            'n_forest': n_forest,
            'n_urban': n_urban,
            'n_mixed': n_mixed,
        },
    })


# =============================================================================
# GENERATE PREVIEW ENDPOINT
# =============================================================================

@api_view(['POST'])
@permission_classes([IsBearerAuthenticated])
def generate_preview(request):
    """
    POST /api/research/generate-preview/

    Queues geometry generation (01_generate_voronoi.R) and OSM features
    (research/03_osm_features.R) as a Celery task to avoid blocking the
    ASGI worker.

    Request body:
        geometry_type (str): 'grid_500' or 'voronoi'

    Returns:
        202 Accepted with task_id and poll_url
    """
    from .tasks_research import run_preview_pipeline

    geometry_type = request.data.get('geometry_type', 'grid_500')
    try:
        target_table = validate_geometry_type(geometry_type)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=400)

    logger.info(f"generate_preview: queuing task for geometry_type={geometry_type}, table={target_table}")

    task = run_preview_pipeline.delay(geometry_type, target_table)

    return Response(
        {
            'task_id': task.id,
            'status': 'queued',
            'poll_url': f'/api/research/preview-status/{task.id}/',
        },
        status=202,
    )


@api_view(['GET'])
@permission_classes([IsBearerAuthenticated])
def preview_status(request, task_id):
    """
    GET /api/research/preview-status/<task_id>/

    Poll the state of a queued generate_preview task.

    Returns:
        {
            "task_id": "...",
            "state": "PENDING" | "STARTED" | "SUCCESS" | "FAILURE",
            "result": {...}   # only when SUCCESS or FAILURE
        }
    """
    from celery.result import AsyncResult

    result = AsyncResult(task_id)
    state = result.state

    payload = {'task_id': task_id, 'state': state}

    if state == 'SUCCESS':
        payload['result'] = result.result
    elif state == 'FAILURE':
        payload['result'] = {'error': str(result.result)}

    return Response(payload)


# =============================================================================
# IMPACTS ENDPOINT (SAR/SDM only)
# =============================================================================

@api_view(['GET'])
def spatial_impacts(request):
    """
    GET /api/research/impacts/ — retrieve impacts from last SAR/SDM model.

    Returns direct, indirect, and total effects for each predictor.
    Only available for SAR/SDM models (SEM/OLS don't need impacts).

    Reference: LeSage & Pace (2009) "Introduction to Spatial Econometrics"
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT model_type, impacts_json, computed_at, aic, rho
            FROM analytics_spatial_result
            WHERE impacts_json IS NOT NULL
            ORDER BY computed_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()

    if not row:
        return Response({
            'available': False,
            'message': 'No impacts available. Run SAR or SDM model first (SEM/OLS do not require impacts).',
        }, status=404)

    return Response({
        'available': True,
        'model_type': row[0],
        'impacts': row[1],
        'computed_at': row[2].isoformat() if row[2] else None,
        'aic': row[3],
        'rho': row[4],
        'interpretation': {
            'direct': 'Effect of X_i change on Y_i (with spatial feedback)',
            'indirect': 'Spillover effect on neighbors when X_i changes',
            'total': 'Direct + Indirect (total system effect)',
        },
    })


def _get_distributions_data(geometry_type: str, forest_threshold: float, building_threshold: float):
    """
    Helper function to get distributions data.
    Used by both distributions() and generate_preview() endpoints.
    """
    try:
        table = validate_geometry_type(geometry_type)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=400)
    n_buckets = 20
    bucket_width = 1.0 / n_buckets

    with connection.cursor() as cursor:
        # Check if table exists and has data
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            n_cells = cursor.fetchone()[0] or 0
        except Exception:
            return Response({
                'geometry_type': geometry_type,
                'n_cells': 0,
                'available': False,
                'message': f'Brak danych. Kliknij "Odswiez" aby wygenerowac.',
            })

        if n_cells == 0:
            return Response({
                'geometry_type': geometry_type,
                'n_cells': 0,
                'available': False,
                'message': f'Brak danych. Kliknij "Odswiez" aby wygenerowac.',
            })

        # Get last update timestamp
        try:
            cursor.execute(f"SELECT MAX(updated_at) FROM {table}")
            last_update = cursor.fetchone()[0]
        except Exception:
            last_update = None

        # Get basic stats and total count
        cursor.execute(f"""
            SELECT
                COUNT(*) as n_cells,
                MIN(COALESCE(forest_cover, 0)) as forest_min,
                MAX(COALESCE(forest_cover, 0)) as forest_max,
                AVG(COALESCE(forest_cover, 0)) as forest_mean,
                MIN(COALESCE(building_density, 0)) as building_min,
                MAX(COALESCE(building_density, 0)) as building_max,
                AVG(COALESCE(building_density, 0)) as building_mean
            FROM {table}
        """)
        row = cursor.fetchone()
        n_cells = row[0] or 0
        forest_stats = {
            'min': row[1] or 0,
            'max': row[2] or 0,
            'mean': row[3] or 0,
        }
        building_stats = {
            'min': row[4] or 0,
            'max': row[5] or 0,
            'mean': row[6] or 0,
        }

        # Get forest_cover histogram buckets
        cursor.execute(f"""
            SELECT
                width_bucket(COALESCE(forest_cover, 0), 0, 1.0001, %s) as bucket,
                COUNT(*) as count
            FROM {table}
            GROUP BY bucket
            ORDER BY bucket
        """, [n_buckets])
        forest_raw = {r[0]: r[1] for r in cursor.fetchall()}

        # Get building_density histogram buckets
        cursor.execute(f"""
            SELECT
                width_bucket(COALESCE(building_density, 0), 0, 1.0001, %s) as bucket,
                COUNT(*) as count
            FROM {table}
            GROUP BY bucket
            ORDER BY bucket
        """, [n_buckets])
        building_raw = {r[0]: r[1] for r in cursor.fetchall()}

        # Regime preview: count cells by regime classification
        cursor.execute(f"""
            SELECT
                SUM(CASE
                    WHEN COALESCE(forest_cover, 0) >= %s
                         AND COALESCE(building_density, 0) < %s
                    THEN 1 ELSE 0 END) as n_forest,
                SUM(CASE
                    WHEN COALESCE(building_density, 0) >= %s
                         AND COALESCE(forest_cover, 0) < %s
                    THEN 1 ELSE 0 END) as n_urban,
                SUM(CASE
                    WHEN NOT (
                        (COALESCE(forest_cover, 0) >= %s AND COALESCE(building_density, 0) < %s)
                        OR (COALESCE(building_density, 0) >= %s AND COALESCE(forest_cover, 0) < %s)
                    )
                    THEN 1 ELSE 0 END) as n_mixed
            FROM {table}
        """, [
            forest_threshold, building_threshold,
            building_threshold, forest_threshold,
            forest_threshold, building_threshold,
            building_threshold, forest_threshold
        ])
        regime_row = cursor.fetchone()
        n_forest = regime_row[0] or 0
        n_urban = regime_row[1] or 0
        n_mixed = regime_row[2] or 0

    # Build bucket arrays
    forest_buckets = []
    building_buckets = []
    for i in range(1, n_buckets + 1):
        from_val = (i - 1) * bucket_width
        to_val = i * bucket_width
        forest_buckets.append({
            'from': round(from_val, 3),
            'to': round(to_val, 3),
            'count': forest_raw.get(i, 0),
        })
        building_buckets.append({
            'from': round(from_val, 3),
            'to': round(to_val, 3),
            'count': building_raw.get(i, 0),
        })

    return Response({
        'geometry_type': geometry_type,
        'n_cells': n_cells,
        'available': True,
        'last_update': last_update.isoformat() if last_update else None,
        'forest_cover': {
            'min': round(forest_stats['min'], 4),
            'max': round(forest_stats['max'], 4),
            'mean': round(forest_stats['mean'], 4),
            'buckets': forest_buckets,
        },
        'building_density': {
            'min': round(building_stats['min'], 4),
            'max': round(building_stats['max'], 4),
            'mean': round(building_stats['mean'], 4),
            'buckets': building_buckets,
        },
        'regime_preview': {
            'forest_threshold': forest_threshold,
            'building_threshold': building_threshold,
            'n_forest': n_forest,
            'n_urban': n_urban,
            'n_mixed': n_mixed,
        },
    })
