"""
GWR Task with DEBUG-FIRST logging.
"""

import os
import subprocess
import tempfile
import uuid
import logging
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import connection

from analytics.debug_mode import DebugLogger
from analytics.models_config import check_n_minimum

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="analytics.tasks_gwr.compute_gwr",
    queue="q_r",
    soft_time_limit=6900,
    time_limit=7200,
    max_retries=2,
    default_retry_delay=300,
)
def compute_gwr(self, run_id: str = None):
    """
    Compute GWR with DEBUG-FIRST logging.
    """
    run_id = run_id or str(uuid.uuid4())[:12]
    debug = DebugLogger(run_id, mode="PUB", module="GWR")

    # Check N minimum
    t = debug.start("check_n_minimum", "Checking data requirements")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM sightings_sighting WHERE status = 'verified'"
        )
        n_obs = cursor.fetchone()[0]

    n_check = check_n_minimum(n_obs, "gwr")
    debug.success(
        "check_n_minimum",
        f"Found {n_obs} observations",
        values={"n_obs": n_obs},
        start_time=t,
    )

    if n_check["error"]:
        debug.warning("check_n_minimum", n_check["message"])
        debug.summary()
        return {"status": "skipped", "reason": n_check["message"], "run_id": run_id}

    try:
        # Prepare R script
        t = debug.start("prepare_r", "Preparing R environment")
        r_script = "/app/r_scripts/compute_gwr.R"

        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as f:
            output_path = f.name

        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = "1"
        env["DB_POOL"] = "dziki_gwr"
        env["RUN_ID"] = run_id

        debug.success(
            "prepare_r",
            "R environment ready",
            values={"script": r_script, "run_id": run_id},
            start_time=t,
        )

        # Run R script
        t = debug.start("run_r", "Executing R GWR computation")
        result = subprocess.run(
            ["Rscript", r_script, "--output", output_path],
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
            debug.success(
                "run_r",
                "GWR computation successful",
                values={"output": output_path},
                start_time=t,
            )
            summary = debug.summary()
            return {
                "status": "success",
                "output": output_path,
                "run_id": run_id,
                "_debug_summary": summary,
            }

        elif result.returncode == 2:
            debug.warning("run_r", "Insufficient data for GWR")
            debug.summary()
            return {
                "status": "skipped",
                "reason": "insufficient_data",
                "run_id": run_id,
            }

        elif result.returncode == 3:
            debug.warning("run_r", "GWR convergence failed, will retry")
            debug.summary()
            raise self.retry(exc=Exception("GWR convergence failed"))

        else:
            debug.error("run_r", f"R script failed: {result.stderr[:200]}")
            debug.summary()
            raise Exception(f"R script failed with code {result.returncode}")

    except SoftTimeLimitExceeded:
        debug.error("timeout", "Soft time limit exceeded")
        debug.summary()
        raise

    except subprocess.TimeoutExpired:
        debug.error("timeout", "R subprocess timeout")
        debug.summary()
        raise self.retry(exc=Exception("R subprocess timeout"))

    except Exception as exc:
        debug.error("task_failed", f"GWR error: {str(exc)}")
        debug.summary()
        raise
