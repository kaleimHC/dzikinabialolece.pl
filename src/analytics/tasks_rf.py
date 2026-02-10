"""
Random Forest task for computing RF predictions.
Weight in ensemble: 0.30

DEBUG-FIRST: Kazdy krok logowany automatycznie!
"""

from celery import shared_task
import numpy as np
import logging
import uuid
from django.db import connection
from analytics.sql_injection_patch import validate_grid_type

from analytics.debug_mode import DebugLogger

logger = logging.getLogger(__name__)

RF_FEATURES = [
    'distance_to_water',
    'forest_cover',
    'building_density',
    'road_density',
    'scrub_cover',
    'meadow_cover',
    'park_cover',
    'barrier_resistance',
]


@shared_task(
    bind=True,
    name='analytics.tasks_rf.compute_rf',
    queue='q_cpu',
    soft_time_limit=300,
    time_limit=600,
    max_retries=2,
    default_retry_delay=30,
)
def compute_rf(self, grid_type: str = 'voronoi', run_id: str = None):
    """DEBUG-FIRST RF computation."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler

    run_id = run_id or str(uuid.uuid4())[:12]
    debug = DebugLogger(run_id, mode='FAST', module='RF')
    grid_table = validate_grid_type(grid_type)

    try:
        t = debug.start('load_data', f'Loading {grid_type} cells')
        with connection.cursor() as cursor:
            feature_cols = ', '.join(RF_FEATURES)
            cursor.execute(f'SELECT id, {feature_cols}, sighting_count FROM {grid_table}')
            rows = cursor.fetchall()
        debug.success('load_data', f'Loaded {len(rows)} cells', values={'count': len(rows), 'grid_type': grid_type}, start_time=t)

        if len(rows) < 10:
            debug.error('load_data', f'Too few cells: {len(rows)}')
            debug.summary()
            return {'status': 'error', 'message': f'Too few cells: {len(rows)}'}

        t = debug.start('prepare_features', 'Extracting features')
        cell_ids, X, y = [], [], []
        skipped = {'all_null': 0, 'all_zero': 0}

        for row in rows:
            cell_id = row[0]
            features = row[1:-1]
            sighting_count = row[-1] or 0
            if all(f is None for f in features):
                skipped['all_null'] += 1
                continue
            if all(f is None or f == 0 for f in features):
                skipped['all_zero'] += 1
                continue
            features = [float(f) if f is not None else 0.0 for f in features]
            cell_ids.append(cell_id)
            X.append(features)
            y.append(1 if sighting_count > 0 else 0)

        X = np.array(X)
        y = np.array(y)

        debug.success('prepare_features', f'{len(X)} valid samples', values={
            'total_cells': len(rows), 'valid_cells': len(X),
            'skipped_null': skipped['all_null'], 'skipped_zero': skipped['all_zero'],
            'positive_samples': int(sum(y)), 'negative_samples': int(len(y) - sum(y)),
            'class_balance': round(float(sum(y) / len(y)), 3) if len(y) > 0 else 0,
        }, start_time=t)

        if len(X) < 10:
            debug.error('prepare_features', f'Not enough valid features: {len(X)}')
            debug.summary()
            return {'status': 'error'}

        debug.inspect('feature_matrix', X)

        feature_stats = {}
        for i, feat in enumerate(RF_FEATURES):
            col = X[:, i]
            feature_stats[feat] = {'min': round(float(col.min()), 4), 'max': round(float(col.max()), 4), 'mean': round(float(col.mean()), 4), 'zeros': int((col == 0).sum())}
        debug.info('feature_stats', 'Feature distributions', values=feature_stats)

        t = debug.start('train_model', 'Training RandomForest')
        if sum(y) == 0:
            debug.warning('train_model', 'No positive samples!', values={'positive': 0, 'negative': len(y)})
            probs = np.random.uniform(0.1, 0.3, size=len(X))
            feature_importances = None
        elif sum(y) == len(y):
            debug.warning('train_model', 'All samples positive!', values={'positive': len(y), 'negative': 0})
            probs = np.random.uniform(0.7, 0.9, size=len(X))
            feature_importances = None
        else:
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            rf = RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_split=5, min_samples_leaf=2, class_weight='balanced', random_state=42, n_jobs=-1)
            rf.fit(X_scaled, y)
            probs = rf.predict_proba(X_scaled)[:, 1] if len(rf.classes_) > 1 else np.full(len(X), 0.5)
            feature_importances = dict(zip(RF_FEATURES, [round(float(f), 4) for f in rf.feature_importances_]))

        debug.success('train_model', 'Model trained', values={'n_estimators': 200, 'max_depth': 8, 'n_samples': len(X), 'feature_importances': feature_importances}, start_time=t)

        debug.inspect('predictions', probs)
        debug.info('prediction_stats', 'Prediction distribution', values={'count': len(probs), 'min': round(float(probs.min()), 4), 'max': round(float(probs.max()), 4), 'mean': round(float(probs.mean()), 4), 'std': round(float(probs.std()), 4)})

        t = debug.start('save_results', f'Saving {len(cell_ids)} predictions')
        with connection.cursor() as cursor:
            update_data = list(zip([float(p) for p in probs], cell_ids))
            cursor.executemany(f'UPDATE {grid_table} SET rf_score = %s, updated_at = NOW() WHERE id = %s', update_data)
        debug.success('save_results', f'Updated {len(update_data)} cells', values={'updated': len(update_data), 'table': grid_table}, start_time=t)

        t = debug.start('verify', 'Verifying saved data')
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT AVG(rf_score), MIN(rf_score), MAX(rf_score), STDDEV(rf_score), COUNT(DISTINCT rf_score), COUNT(*) FROM {grid_table} WHERE rf_score IS NOT NULL')
            stats = cursor.fetchone()
        verification = {'rf_mean': round(float(stats[0]), 4) if stats[0] else None, 'rf_min': round(float(stats[1]), 4) if stats[1] else None, 'rf_max': round(float(stats[2]), 4) if stats[2] else None, 'rf_std': round(float(stats[3]), 4) if stats[3] else None, 'unique_values': stats[4] or 0, 'total_with_rf': stats[5] or 0}

        if verification['unique_values'] > 10:
            debug.success('verify', 'Verification passed - good variance', values=verification, start_time=t)
        else:
            debug.warning('verify', f"Low variance: only {verification['unique_values']} unique values", values=verification)

        summary = debug.summary()
        return {'status': 'success', 'grid_type': grid_type, 'run_id': run_id, 'n_cells': len(update_data), **verification, '_debug_summary': summary}

    except Exception as exc:
        debug.error('task_failed', f'RF error: {str(exc)}')
        debug.summary()
        logger.exception(f'RF error: {exc}')
        raise self.retry(exc=exc)
