"""
Celery Tasks for Analytics app.
MASTER_SPEC v2.2 Architecture

Task routing:
- q_r: R Spatial (GWR, ETA, STS) -> worker-r
- q_cpu: Python ML (RF, Ensemble) -> worker-py
- q_io: I/O (MV refresh, tiles) -> worker-io

CRITICAL for R tasks:
- Worker must use --pool=prefork --max-tasks-per-child=1
- Environment: OMP_NUM_THREADS=1
"""

import os
import subprocess
import tempfile
import json
from celery import shared_task
from .tasks_bayesian import check_n_minimum
from celery.exceptions import SoftTimeLimitExceeded
from django.core.cache import cache
from django.db import connection
import logging
import uuid

from analytics.debug_mode import DebugLogger

logger = logging.getLogger(__name__)


# =============================================================================
# R SPATIAL TASKS (queue: q_r)
# =============================================================================

@shared_task(
    bind=True,
    queue='q_r',
    soft_time_limit=6900,   # 115 min (soft)
    time_limit=7200,        # 120 min (hard)
    max_retries=2,
    default_retry_delay=300,
)
def compute_gwr_weekly(self):
    """
    Compute Geographically Weighted Regression (GWR) weekly.
    
    Calls R script via subprocess.
    Uses dziki_gwr pool (Session mode) for long-running queries.
    
    Exit codes:
    - 0: Success
    - 1: General error
    - 2: Data insufficient
    - 3: Convergence failed
    """
    logger.info(f"Starting GWR computation (task_id={self.request.id})")
    
    # Check N minimum requirements (MASTER_SPEC v2.2)
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM sightings_sighting WHERE status = 'verified'")
        n_obs = cursor.fetchone()[0]
    
    n_check = check_n_minimum(n_obs, 'gwr')
    if n_check['error']:
        logger.warning(f"GWR: {n_check['message']}")
        return {'status': 'skipped', 'reason': n_check['message']}
    
    try:
        # Prepare R script path
        r_script = '/app/r_scripts/compute_gwr.R'
        
        # Output file for results
        with tempfile.NamedTemporaryFile(suffix='.geojson', delete=False) as f:
            output_path = f.name
        
        # Run R script
        env = os.environ.copy()
        env['OMP_NUM_THREADS'] = '1'  # Prevent thread contention
        env['DB_POOL'] = 'dziki_gwr'  # Use session pool
        
        result = subprocess.run(
            ['Rscript', r_script, '--output', output_path],
            env=env,
            capture_output=True,
            text=True,
            timeout=7000,  # Just under hard limit
        )
        
        # Handle exit codes
        if result.returncode == 0:
            logger.info("GWR computation completed successfully")
            # TODO: Store results in database
            return {'status': 'success', 'output': output_path}
        
        elif result.returncode == 2:
            logger.warning("GWR: Insufficient data")
            return {'status': 'skipped', 'reason': 'insufficient_data'}
        
        elif result.returncode == 3:
            logger.warning("GWR: Convergence failed, retrying...")
            raise self.retry(exc=Exception("GWR convergence failed"))
        
        else:
            logger.error(f"GWR failed: {result.stderr}")
            raise Exception(f"R script failed with code {result.returncode}")
    
    except SoftTimeLimitExceeded:
        logger.error("GWR: Soft time limit exceeded, cleaning up...")
        # Cleanup logic here
        raise
    
    except subprocess.TimeoutExpired:
        logger.error("GWR: Subprocess timeout")
        raise self.retry(exc=Exception("R subprocess timeout"))
    
    except Exception as exc:
        logger.exception(f"GWR error: {exc}")
        raise


@shared_task(
    bind=True,
    queue='q_r',
    soft_time_limit=6900,
    time_limit=7200,
    max_retries=2,
)
def compute_eta(self, grid_id: str = None):
    """
    Compute Entropy-Tessellation-Agglomeration (ETA).
    
    Uses spatialWarsaw::ETA() via R subprocess.
    """
    logger.info(f"Starting ETA computation (grid_id={grid_id})")
    
    # Check N minimum requirements (MASTER_SPEC v2.2)
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM sightings_sighting WHERE status = 'verified'")
        n_obs = cursor.fetchone()[0]
    
    n_check = check_n_minimum(n_obs, 'eta')
    if n_check['error']:
        logger.warning(f"ETA: {n_check['message']}")
        return {'status': 'skipped', 'reason': n_check['message']}
    
    try:
        r_script = '/app/r_scripts/compute_eta.R'
        
        env = os.environ.copy()
        env['OMP_NUM_THREADS'] = '1'
        env['DB_POOL'] = 'dziki_gwr'
        
        cmd = ['Rscript', r_script]
        if grid_id:
            cmd.extend(['--grid-id', grid_id])
        
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=7000,
        )
        
        if result.returncode == 0:
            return {'status': 'success'}
        else:
            raise Exception(f"ETA failed: {result.stderr}")
    
    except Exception as exc:
        logger.exception(f"ETA error: {exc}")
        raise


@shared_task(
    bind=True,
    queue='q_r',
    soft_time_limit=13800,  # 230 min (STS can run up to 240 min)
    time_limit=14400,       # 240 min
    max_retries=1,
)
def compute_sts(self, year: int = None):
    """
    Compute Spatio-Temporal Stability (STS).
    
    Uses spatialWarsaw::STS() - can run up to 4 hours!
    """
    logger.info(f"Starting STS computation (year={year})")
    
    try:
        r_script = '/app/r_scripts/compute_sts.R'
        
        env = os.environ.copy()
        env['OMP_NUM_THREADS'] = '1'
        env['DB_POOL'] = 'dziki_gwr'
        
        cmd = ['Rscript', r_script]
        if year:
            cmd.extend(['--year', str(year)])
        
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=14000,
        )
        
        if result.returncode == 0:
            return {'status': 'success'}
        else:
            raise Exception(f"STS failed: {result.stderr}")
    
    except Exception as exc:
        logger.exception(f"STS error: {exc}")
        raise


# =============================================================================
# PYTHON ML TASKS (queue: q_cpu)
# =============================================================================

@shared_task(
    bind=True,
    queue='q_cpu',
    soft_time_limit=1800,   # 30 min
    time_limit=2100,        # 35 min
    max_retries=3,
)
def train_random_forest(self):
    """
    Train Random Forest model for ensemble prediction.
    
    Pure Python task using scikit-learn.
    """
    logger.info("Starting Random Forest training")
    
    try:
        # TODO: Implement RF training
        # from sklearn.ensemble import RandomForestRegressor
        # ...
        
        return {'status': 'success', 'model': 'random_forest'}
    
    except Exception as exc:
        logger.exception(f"RF training error: {exc}")
        raise


@shared_task(
    bind=True,
    queue='q_cpu',
    soft_time_limit=600,
    time_limit=900,
)
def compute_ensemble(self, model_ids: list = None):
    """
    Compute ensemble prediction from GWR + RF models.
    """
    logger.info(f"Starting ensemble computation (models={model_ids})")
    
    try:
        # TODO: Implement ensemble logic
        return {'status': 'success'}
    
    except Exception as exc:
        logger.exception(f"Ensemble error: {exc}")
        raise


# =============================================================================
# I/O TASKS (queue: q_io)
# =============================================================================

@shared_task(
    bind=True,
    queue='q_io',
    soft_time_limit=300,
    time_limit=600,
)
def refresh_materialized_views(self):
    """
    Refresh materialized views concurrently.
    
    Uses: REFRESH MATERIALIZED VIEW CONCURRENTLY
    """
    logger.info("Starting MV refresh")
    
    try:
        with connection.cursor() as cursor:
            # Refresh sighting stats MV
            cursor.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY IF EXISTS mv_sighting_stats;"
            )
            # Refresh grid stats MV
            cursor.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY IF EXISTS mv_grid_stats;"
            )
        
        # Invalidate related caches
        cache.delete('sighting_stats')
        cache.delete('grid_stats')
        
        logger.info("MV refresh completed")
        return {'status': 'success'}
    
    except Exception as exc:
        logger.exception(f"MV refresh error: {exc}")
        raise


@shared_task(queue='q_io')
def generate_tiles(zoom_levels: list = None):
    """
    Generate vector tiles for map display.
    """
    logger.info(f"Starting tile generation (zoom={zoom_levels})")
    
    try:
        # TODO: Implement tile generation (tippecanoe or similar)
        return {'status': 'success'}
    
    except Exception as exc:
        logger.exception(f"Tile generation error: {exc}")
        raise


@shared_task(queue='q_io')
def warmup_cache():
    """
    Warm up frequently accessed cache entries.
    """
    logger.info("Starting cache warmup")
    
    try:
        from sightings.models import Sighting
        from django.utils import timezone
        from datetime import timedelta
        
        # Pre-compute and cache stats
        queryset = Sighting.objects.filter(status=Sighting.Status.VERIFIED)
        week_ago = timezone.now() - timedelta(days=7)
        month_ago = timezone.now() - timedelta(days=30)
        
        stats = {
            'total': queryset.count(),
            'last_7_days': queryset.filter(observed_at__gte=week_ago).count(),
            'last_30_days': queryset.filter(observed_at__gte=month_ago).count(),
        }
        
        cache.set('sighting_stats', stats, timeout=3600)
        
        logger.info("Cache warmup completed")
        return {'status': 'success', 'stats': stats}
    
    except Exception as exc:
        logger.exception(f"Cache warmup error: {exc}")
        raise


# =============================================================================
# DEV: Full R Pipeline (on-demand recalculation)
# =============================================================================

@shared_task(
    bind=True,
    queue='q_cpu',  # Runs on worker-py with docker socket access
    soft_time_limit=1800,  # 30 min total
    time_limit=2100,       # 35 min hard limit
)
def run_r_pipeline_dev(self):
    """
    Run full R pipeline sequentially for dev recalculation.

    Uses Docker SDK to execute R scripts in worker-r container.

    Runs all 4 R scripts in order:
    1. 01_generate_voronoi.R
    2. 02_compute_tessw_eta.R
    3. 04_compute_gwr.R
    4. 05_ensemble_prediction.R
    """
    # ═══════════════════════════════════════════════════════════════
    # DISABLED: 2026-01-18 - Under rewrite according to Kopczewska
    # Re-enable after completing spatialWarsaw integration
    # See: HANDOFF_03_IMPLEMENTATION_PLAN.md
    # ═══════════════════════════════════════════════════════════════
    from django.core.cache import cache
    cache.set('r_pipeline_progress', {
        'running': False,
        'current_step': 0,
        'total_steps': 5,
        'current_script': '',
        'error': 'PUB pipeline wyłączony - w trakcie przepisywania według metodologii Kopczewskiej. Użyj trybu FAST.',
        'completed': False,
        'disabled': True,
    }, timeout=3600)
    cache.delete('recalculate_lock')
    return {
        'status': 'disabled',
        'message': 'PUB pipeline wyłączony - w trakcie przepisywania według metodologii Kopczewskiej. Użyj trybu FAST.',
        'redirect': 'fast',
        'disabled_at': '2026-01-18',
        'reason': 'Rewrite in progress'
    }

    import docker
    from django.core.cache import cache

    scripts = [
        ('01_generate_voronoi.R', 'Generowanie Voronoi tessellation'),
        ('02_compute_tessw_eta.R', 'Obliczanie tessW + ETA'),
        ('04_compute_gwr.R', 'Obliczanie GWR'),
        ('05_ensemble_prediction.R', 'Ensemble prediction'),
    ]

    total_steps = len(scripts)

    # Initialize Docker client
    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        error_msg = f'Docker not available: {str(e)}'
        logger.error(error_msg)
        cache.set('r_pipeline_progress', {
            'running': False,
            'current_step': 0,
            'total_steps': total_steps,
            'current_script': '',
            'error': error_msg,
            'completed': False,
        }, timeout=3600)
        cache.delete('recalculate_lock')  # Release lock on error
        raise Exception(error_msg)

    for i, (script, description) in enumerate(scripts, 1):
        # Update progress in cache
        cache.set('r_pipeline_progress', {
            'running': True,
            'current_step': i,
            'total_steps': total_steps,
            'current_script': description,
            'error': None,
            'completed': False,
        }, timeout=3600)

        logger.info(f"Running {script} ({i}/{total_steps}): {description}")

        try:
            # Use Docker SDK to run R script in worker-r container
            # Connect to dziki-internal network for direct db access
            container = client.containers.run(
                'dziki-worker-r:latest',
                command=['Rscript', '--vanilla', f'/app/r_scripts/{script}'],
                environment={
                    'DB_HOST': 'db',
                    'DB_PORT': '5432',
                    'DB_NAME': os.environ.get('DB_NAME', 'dziki_db'),
                    'DB_USER': os.environ.get('DB_USER', 'dziki'),
                    'DB_PASSWORD': os.environ.get('DB_PASSWORD', 'dziki_dev_password'),
                    'OMP_NUM_THREADS': '1',
                },
                network='dziki_dziki-internal',
                volumes={
                    'dziki_r_data': {'bind': '/app/data', 'mode': 'rw'},
                },
                remove=True,
                detach=False,
                stdout=True,
                stderr=True,
            )

            output = container.decode('utf-8') if isinstance(container, bytes) else str(container)
            logger.info(f"Completed {script}")
            logger.debug(f"R output: {output[:500]}")

        except docker.errors.ContainerError as e:
            error_msg = f'{script}: {e.stderr.decode("utf-8")[:500] if e.stderr else str(e)}'
            logger.error(f"R script failed: {error_msg}")
            cache.set('r_pipeline_progress', {
                'running': False,
                'current_step': i,
                'total_steps': total_steps,
                'current_script': description,
                'error': error_msg,
                'completed': False,
            }, timeout=3600)
            cache.delete('recalculate_lock')  # Release lock on error
            raise Exception(error_msg)

        except Exception as e:
            error_msg = f'{script}: {str(e)}'
            logger.error(f"R script error: {error_msg}")
            cache.set('r_pipeline_progress', {
                'running': False,
                'current_step': i,
                'total_steps': total_steps,
                'current_script': description,
                'error': error_msg,
                'completed': False,
            }, timeout=3600)
            cache.delete('recalculate_lock')  # Release lock on error
            raise Exception(error_msg)

    # Mark as completed
    cache.set('r_pipeline_progress', {
        'running': False,
        'current_step': total_steps,
        'total_steps': total_steps,
        'current_script': 'Zakończono',
        'error': None,
        'completed': True,
    }, timeout=3600)
    cache.delete('recalculate_lock')  # Release lock on success

    logger.info("R pipeline completed successfully")
    return {'status': 'success', 'steps_completed': total_steps}


# =============================================================================
# RISK PREDICTION (simplified for MVP)
# =============================================================================

@shared_task(queue='q_cpu')
def generate_risk_predictions():
    """
    Generate simplified risk predictions for heatmap.

    Temporary implementation using heuristic:
    risk = normalize(sighting_count) + random_noise

    To be replaced with real GWR/Ensemble later.
    """
    import random
    from datetime import date
    from sightings.models import GridCell
    from analytics.models import ModelPrediction

    logger.info("Starting risk prediction generation")

    try:
        grid_cells = GridCell.objects.all()
        today = date.today()
        created = 0

        for cell in grid_cells:
            # Simple heuristic: more sightings = higher risk
            base_risk = min(cell.sighting_count / 10.0, 1.0)
            noise = random.uniform(-0.1, 0.1)
            risk = max(0, min(1, base_risk + noise))

            ModelPrediction.objects.update_or_create(
                grid_cell=cell,
                model_type='ensemble',
                prediction_date=today,
                defaults={
                    'prediction_value': risk,
                    'confidence_lower': max(0, risk - 0.15),
                    'confidence_upper': min(1, risk + 0.15),
                    'model_version': 'heuristic-v1',
                }
            )
            created += 1

        logger.info(f"Created/updated {created} predictions")
        return {'status': 'success', 'predictions': created}

    except Exception as exc:
        logger.exception(f"Risk prediction error: {exc}")
        raise


# =============================================================================
# RECALCULATE RISK MODEL (Python-based, no R required)
# =============================================================================

@shared_task(bind=True, queue='q_cpu', soft_time_limit=120, time_limit=180)
def recalculate_risk_model(self):
    """
    FAST risk recalculation - uses SQUARE GRID (sightings_gridcell_square).

    IZOLACJA: NIE modyfikuje sightings_gridcell_voronoi (PUB mode data)!
    Expected: ~30s
    """
    logger.info("Starting FAST risk model recalculation (sightings_gridcell_square)")

    try:
        with connection.cursor() as cursor:
            cache.set('r_pipeline_progress', {
                'running': True, 'current_step': 1, 'total_steps': 4,
                'current_script': 'Zliczanie obserwacji (SQUARE)', 'error': None, 'completed': False,
            }, timeout=3600)

            # FAST mode: count sightings per SQUARE grid cell
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
            new_assigned = cursor.rowcount

            cache.set('r_pipeline_progress', {
                'running': True, 'current_step': 2, 'total_steps': 4,
                'current_script': 'Obliczanie gestosci', 'error': None, 'completed': False,
            }, timeout=3600)

            cache.set('r_pipeline_progress', {
                'running': True, 'current_step': 3, 'total_steps': 4,
                'current_script': 'Obliczanie ryzyka', 'error': None, 'completed': False,
            }, timeout=3600)

            # Fixed thresholds based on data distribution (replaces PERCENT_RANK)
            cursor.execute("UPDATE sightings_gridcell_square SET sighting_density = sighting_count / NULLIF(ST_Area(ST_Transform(geometry, 2180)) / 1000000.0, 0);")
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
                    END;
            """)
            cursor.execute("UPDATE sightings_gridcell_square SET confidence = CASE WHEN sighting_count = 0 THEN 0.2 WHEN sighting_count < 3 THEN 0.4 WHEN sighting_count < 6 THEN 0.6 ELSE 0.8 END;")

            # Spatial smoothing - row-standardized weights
            cache.set('r_pipeline_progress', {
                'running': True, 'current_step': 4, 'total_steps': 4,
                'current_script': 'Smoothing row-standardized (W)', 'error': None, 'completed': False,
            }, timeout=3600)

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

            # Update timestamp
            cursor.execute("UPDATE sightings_gridcell_square SET updated_at = NOW();")

            cursor.execute("SELECT COUNT(*) FILTER (WHERE ensemble_risk >= 0.7) FROM sightings_gridcell_square;")
            critical = cursor.fetchone()[0]
            cache.delete('sighting_stats')

        cache.set('r_pipeline_progress', {
            'running': False, 'current_step': 4, 'total_steps': 4,
            'current_script': 'Zakonczone', 'error': None, 'completed': True,
        }, timeout=3600)
        # Release lock to allow new recalculation
        cache.delete('recalculate_lock')

        logger.info(f"Fast recalc (SQUARE): {new_assigned} new, {critical} critical")
        return {'status': 'success', 'new_sightings': new_assigned, 'critical_cells': critical}

    except Exception as exc:
        cache.set('r_pipeline_progress', {
            'running': False, 'current_step': 0, 'total_steps': 4,
            'current_script': '', 'error': str(exc), 'completed': False,
        }, timeout=3600)
        # Release lock even on error
        cache.delete('recalculate_lock')
        raise


# =============================================================================
# SAMPLE SWITCHING (Test datasets)
# =============================================================================

SAMPLE_FILES = {
    'mala': 'baza_mala.json',
    'srednia': 'baza_srednia.json',
    'duza': 'baza_duza.json',
    'pelna': 'baza_ogromna.json',
}


@shared_task(bind=True, queue='q_io', soft_time_limit=120, time_limit=180)
def switch_sample_task(self, sample: str):
    """
    Switch to a different sample database.

    Steps:
    1. TRUNCATE sightings
    2. Load fixture
    3. Recalculate grid counts
    4. Verify & notify
    """
    from django.core.management import call_command

    if sample not in SAMPLE_FILES:
        raise ValueError(f"Invalid sample: {sample}")

    fixture_file = f'/fixtures/samples/{SAMPLE_FILES[sample]}'
    total_steps = 4

    def update_progress(step, message):
        cache.set('sample_switch_progress', {
            'running': True,
            'task_id': self.request.id,
            'sample': sample,
            'current': step,
            'total': total_steps,
            'step': message,
            'message': message,
            'error': None,
        }, timeout=600)

    try:
        # Step 1: Truncate
        update_progress(1, 'Czyszczenie danych...')
        logger.info(f"Switching to sample: {sample}")

        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE sightings_sighting CASCADE;")

        # Step 2: Load fixture
        update_progress(2, 'Ładowanie próby...')
        call_command('loaddata', fixture_file, verbosity=0)

        # Step 3: Recalculate grid counts
        update_progress(3, 'Przeliczanie siatki...')

        with connection.cursor() as cursor:
            # Reset all counts
            cursor.execute("UPDATE sightings_gridcell SET sighting_count = 0;")

            # Count sightings per grid cell using spatial join (no grid_cell_id assignment)
            cursor.execute("""
                UPDATE sightings_gridcell g SET sighting_count = COALESCE(subq.cnt, 0)
                FROM (
                    SELECT gc.grid_id, COUNT(s.id) as cnt
                    FROM sightings_gridcell gc
                    LEFT JOIN sightings_sighting s ON ST_Contains(gc.geometry, s.location)
                    WHERE s.status = 'verified' OR s.id IS NULL
                    GROUP BY gc.grid_id
                ) subq
                WHERE g.grid_id = subq.grid_id;
            """)

            # Update density
            # FIX: Use EPSG:2180 for area and sighting_count for ranking (avoids latitude bias)
            cursor.execute("""
                UPDATE sightings_gridcell
                SET sighting_density = sighting_count / NULLIF(ST_Area(ST_Transform(geometry, 2180)) / 1000000.0, 0);
            """)

            # Fixed thresholds based on data distribution (replaces PERCENT_RANK)
            cursor.execute("""
                UPDATE sightings_gridcell
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
                    END;
            """)

        # Step 4: Verify
        update_progress(4, 'Weryfikacja...')

        from sightings.models import Sighting
        final_count = Sighting.objects.count()

        # Clear caches
        cache.delete('sighting_stats')

        # Mark completed
        cache.set('sample_switch_progress', {
            'running': False,
            'task_id': self.request.id,
            'sample': sample,
            'current': total_steps,
            'total': total_steps,
            'step': 'completed',
            'message': f'Załadowano {final_count} obserwacji',
            'error': None,
        }, timeout=600)

        logger.info(f"Sample switch complete: {sample} ({final_count} sightings)")
        return {'status': 'success', 'sample': sample, 'sighting_count': final_count}

    except Exception as exc:
        error_msg = str(exc)
        logger.exception(f"Sample switch error: {error_msg}")

        cache.set('sample_switch_progress', {
            'running': False,
            'task_id': self.request.id,
            'sample': sample,
            'current': 0,
            'total': total_steps,
            'step': 'error',
            'message': 'Błąd',
            'error': error_msg,
        }, timeout=600)

        raise


# =============================================================================
# BAYESIAN LAYER TASKS (MASTER_SPEC v2.3)
# Import to make Celery autodiscover these tasks
# =============================================================================
from analytics.tasks_bayesian import (  # noqa: F401, E402
    elicit_priors,
    compute_bayesian_ssm,
    aggregate_bayesian_ensemble,
    invalidate_bayesian_cache,
    run_bayesian_pipeline,
)

# =============================================================================
# RANDOM FOREST TASK
# =============================================================================
from analytics.tasks_rf import compute_rf  # noqa: F401, E402

# =============================================================================
# GWR TASK (DEBUG-FIRST)
# =============================================================================
from analytics.tasks_gwr import compute_gwr  # noqa: F401, E402

# =============================================================================
# ETA TASK (DEBUG-FIRST)
# =============================================================================
from analytics.tasks_eta import compute_eta as compute_eta_debug  # noqa: F401, E402

# =============================================================================
# GWR HEURISTIC (FAST mode proxy)
# =============================================================================
from analytics.tasks_gwr_heuristic import compute_gwr_heuristic  # noqa: F401, E402

# =============================================================================
# MODE ROUTER (FAST/PUB/BAYES pipeline separation)
# =============================================================================
from analytics.mode_router import run_pipeline, MODE_CONFIG  # noqa: F401, E402

# =============================================================================
# RESEARCH PIPELINE TASK (spatialWarsaw async)
# =============================================================================
from analytics.tasks_research import run_research_pipeline  # noqa: F401, E402
