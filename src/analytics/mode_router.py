"""
MODE ROUTER — FAST/PUB pipeline dispatcher.
"""

import uuid
import logging
from celery import shared_task
from django.db import connection

from analytics.debug_mode import DebugLogger

logger = logging.getLogger(__name__)

# Mode configurations
MODE_CONFIG = {
    "FAST": {
        "grid_type": "square",  # FAST = SQUARE grid (9875 cells)
        "description": "Real-time API responses",
    },
    "PUB": {
        "grid_type": "voronoi",  # PUB = VORONOI grid (100-500 cells)
        "description": "Publication quality (Voronoi + area-rank)",
    },
}


@shared_task(
    bind=True,
    name="analytics.mode_router.run_pipeline",
    queue="q_cpu",
    soft_time_limit=600,
    time_limit=900,
)
def run_pipeline(self, mode: str = "FAST", run_id: str = None):
    """
    Main pipeline router - dispatches to appropriate mode.
    """
    run_id = run_id or str(uuid.uuid4())[:12]
    debug = DebugLogger(run_id, mode=mode, module="MODE_ROUTER")

    if mode not in MODE_CONFIG:
        debug.error(
            "validate_mode",
            f"Unknown mode: {mode}",
            values={"valid_modes": list(MODE_CONFIG.keys())},
        )
        return {"status": "error", "message": f"Unknown mode: {mode}"}

    config = MODE_CONFIG[mode]

    t = debug.start("run_pipeline", f"Starting {mode} pipeline")
    debug.info("config", "Mode configuration", values=config)

    try:
        if mode == "FAST":
            result = _run_fast_pipeline(run_id, config, debug)
        elif mode == "PUB":
            result = _run_pub_pipeline(run_id, config, debug)
        else:
            return {"status": "error", "message": f"Mode {mode} not implemented"}

        debug.success(
            "run_pipeline", f"{mode} pipeline completed", values=result, start_time=t
        )
        result["_debug_summary"] = debug.summary()
        return result

    except Exception as exc:
        debug.error("pipeline_failed", f"{mode} pipeline error: {str(exc)}")
        debug.summary()
        logger.exception(f"{mode} pipeline error: {exc}")
        raise


def _run_fast_pipeline(run_id: str, config: dict, debug: DebugLogger) -> dict:
    """FAST pipeline: simple sighting-based risk on SQUARE grid."""
    return {"status": "ok", "mode": "FAST", "grid_type": config["grid_type"]}


def _run_pub_pipeline(run_id: str, config: dict, debug: DebugLogger) -> dict:
    """PUB pipeline: Voronoi + R spatial models."""
    return {"status": "ok", "mode": "PUB", "grid_type": config["grid_type"]}
