"""
ETA Task with DEBUG-FIRST logging.
"""

import os
import subprocess
import uuid
import logging
from celery import shared_task
from django.db import connection

from analytics.debug_mode import DebugLogger
from analytics.models_config import check_n_minimum

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="analytics.tasks_eta.compute_eta",
    queue="q_r",
    soft_time_limit=6900,
    time_limit=7200,
    max_retries=2,
)
def compute_eta(self, grid_id: str = None, run_id: str = None):
    """
    Compute ETA (Entropy-Tessellation-Agglomeration) with DEBUG-FIRST logging.
    Uses spatialWarsaw::ETA() via R subprocess.
    """
    run_id = run_id or str(uuid.uuid4())[:12]
    debug = DebugLogger(run_id, mode="FAST", module="ETA")

    # Check N minimum
    t = debug.start("check_n_minimum", "Checking data requirements")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM sightings_sighting WHERE status = 'verified'"
        )
        n_obs = cursor.fetchone()[0]

    n_check = check_n_minimum(n_obs, "eta")
    debug.success(
        "check_n_minimum",
        f"Found {n_obs} observations",
        values={"n_obs": n_obs, "grid_id": grid_id},
        start_time=t,
    )

    if n_check["error"]:
        debug.warning("check_n_minimum", n_check["message"])
        debug.summary()
        return {"status": "skipped", "reason": n_check["message"], "run_id": run_id}

    try:
        # Prepare R script
        t = debug.start("prepare_r", "Preparing R environment")
        r_script = "/app/r_scripts/compute_eta.R"

        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = "1"
        env["DB_POOL"] = "dziki_gwr"
        env["RUN_ID"] = run_id

        cmd = ["Rscript", r_script]
        if grid_id:
            cmd.extend(["--grid-id", grid_id])

        debug.success(
            "prepare_r",
            "R environment ready",
            values={"script": r_script, "grid_id": grid_id},
            start_time=t,
        )

        # Run R script
        t = debug.start("run_r", "Executing R ETA computation")
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=7000,
        )

        debug.info(
            "run_r",
            "R script finished",
            values={
                "returncode": result.returncode,
                "stdout_len": len(result.stdout),
                "stderr_len": len(result.stderr),
            },
        )

        if result.returncode == 0:
            # Get ETA stats from DB
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*), MIN(area_rank_score), MAX(area_rank_score), AVG(area_rank_score)
                    FROM sightings_gridcell_voronoi
                    WHERE area_rank_score IS NOT NULL
                """)
                stats = cursor.fetchone()

            verification = {
                "count": stats[0],
                "eta_min": round(float(stats[1]), 4) if stats[1] else None,
                "eta_max": round(float(stats[2]), 4) if stats[2] else None,
                "eta_mean": round(float(stats[3]), 4) if stats[3] else None,
            }

            debug.success(
                "run_r", "ETA computation successful", values=verification, start_time=t
            )
            summary = debug.summary()
            return {
                "status": "success",
                "run_id": run_id,
                **verification,
                "_debug_summary": summary,
            }

        else:
            debug.error("run_r", f"R script failed: {result.stderr[:200]}")
            debug.summary()
            raise Exception(f"ETA failed: {result.stderr}")

    except Exception as exc:
        debug.error("task_failed", f"ETA error: {str(exc)}")
        debug.summary()
        raise
