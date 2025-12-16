"""
Celery Tasks for Analytics app — FAST mode risk computation.
MASTER_SPEC v2.2 Architecture
"""

import logging

logger = logging.getLogger(__name__)

# =============================================================================
# FAST ALGORITHM — Weight Constants
# =============================================================================
# Risk factor weights (must sum to 1.0)
FAST_WEIGHTS = {
    'forest':    0.35,  # Forest proximity (primary habitat)
    'water':     0.25,  # Water body proximity (secondary habitat)
    'roads':     0.20,  # Road density (movement corridors)
    'buildings': 0.10,  # Building density (inverse — less = more risk)
    'barriers':  0.10,  # Barrier permeability (fences, walls)
}

assert abs(sum(FAST_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


def rank_normalize(values):
    """
    Rank normalization: scale array to [0, 1] using percentile ranking.

    spatialWarsaw methodology: score = (rank - 1) / (n - 1)
    Monotonic transformation preserving relative order.
    """
    if not values:
        return []
    n = len(values)
    if n == 1:
        return [0.5]
    sorted_vals = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * n
    for rank, (idx, _) in enumerate(sorted_vals):
        ranks[idx] = rank / (n - 1)
    return ranks


def compute_fast_scores(cells):
    """
    Compute FAST risk scores for grid cells.

    Each dimension is rank-normalized independently, then
    combined with FAST_WEIGHTS.
    """
    if not cells:
        return []

    dims = {
        'forest': [c.get('distance_to_forest', 0) for c in cells],
        'water':  [c.get('distance_to_water', 0) for c in cells],
        'roads':  [c.get('road_density', 0) for c in cells],
    }

    # Invert distance dimensions (closer = higher risk)
    for key in ('forest', 'water'):
        max_val = max(dims[key]) or 1
        dims[key] = [max_val - v for v in dims[key]]

    normalized = {k: rank_normalize(v) for k, v in dims.items()}

    scores = []
    for i in range(len(cells)):
        score = (
            FAST_WEIGHTS['forest'] * normalized['forest'][i] +
            FAST_WEIGHTS['water'] * normalized['water'][i] +
            FAST_WEIGHTS['roads'] * normalized['roads'][i]
        )
        scores.append(round(score, 4))
    return scores
