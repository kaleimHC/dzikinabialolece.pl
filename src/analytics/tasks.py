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
