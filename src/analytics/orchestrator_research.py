"""
Research Pipeline Orchestrator.

Executes the Research Pipeline step-by-step with proper error handling.
Each step is logged to ResearchStepLog. The pipeline stops on first failure.

Exit code conventions (shared with R scripts):
    0   — success
    1   — validation / input error (do not retry)
    2   — timeout (may retry)
    3   — computation error / fallback (graceful degradation)
    137 — OOM killed by kernel
"""

import logging
import os
from typing import Optional

from django.db import connection
from django.utils import timezone

# Channels imports for WebSocket progress updates
try:
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False

from .models_research import (
    ResearchConfig,
    ResearchRun,
    ResearchStepLog,
    StepStatus,
    StepType,
    RunStatus,
)

logger = logging.getLogger(__name__)


# EXCEPTIONS


class PipelineError(Exception):
    """Raised when a pipeline step fails and the pipeline must stop."""

    def __init__(
        self,
        message: str,
        step_name: str = "",
        exit_code: int = 1,
        stdout: str = "",
        stderr: str = "",
    ):
        self.step_name = step_name
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(message)


# PIPELINE STEP DEFINITIONS

PIPELINE_STEPS = [
    {
        "name": "01_geometry",
        "description": "Generate spatial units (Voronoi / grid)",
        "type": StepType.R,
        "script": "01_generate_voronoi.R",
    },
    {
        "name": "02_population",
        "description": "Assign population to spatial units",
        "type": StepType.R,
        "script": "research/02_population.R",
    },
    {
        "name": "03_osm_features",
        "description": "Calculate OSM environmental features",
        "type": StepType.R,
        "script": "research/03_osm_features.R",
    },
    {
        "name": "04_variable_y",
        "description": "Compute dependent variable Y",
        "type": StepType.R,
        "script": "research/04_variable_y.R",
    },
    {
        "name": "05_matrix_w",
        "description": "Build spatial weights matrix W",
        "type": StepType.R,
        "script": "research/05_matrix_w.R",
    },
    {
        "name": "06_model",
        "description": "Fit spatial model (SAR/SEM/SDM/probit/logit)",
        "type": StepType.R,
        "script": "02_spatial_models.R",
    },
    {
        "name": "07_diagnostics",
        "description": "Run diagnostics (Moran's I, LM tests, LISA)",
        "type": StepType.R,
        "script": "research/07_diagnostics.R",
    },
    {
        "name": "08_results",
        "description": "Ensemble prediction and final risk map",
        "type": StepType.R,
        "script": "05_ensemble_prediction.R",
    },
]


# DOCKER RUNNER

# Docker image and network constants (match existing infrastructure)
R_DOCKER_IMAGE = "dziki-worker-r:latest"
DOCKER_NETWORK = "dziki_dziki-internal"


def _build_db_env() -> dict:
    return {
        "DB_HOST": "db",
        "DB_PORT": "5432",
        "DB_NAME": os.environ.get("DB_NAME", "dziki_db"),
        "DB_USER": os.environ.get("DB_USER", "dziki"),
        "DB_PASSWORD": os.environ.get("DB_PASSWORD", "dziki_dev_password"),
        "OMP_NUM_THREADS": "1",
    }


def run_r_script(
    script_name: str,
    extra_env: Optional[dict] = None,
    image: str = R_DOCKER_IMAGE,
    timeout: int = 600,
) -> tuple[int, str, str]:
    """
    Run an R script inside a Docker container.

    Returns (exit_code, stdout, stderr) tuple.
    Extracts exit_status from ContainerError.
    Never silently continues on failure.

    Args:
        script_name: R script filename (e.g. '01_generate_voronoi.R')
        extra_env: Additional environment variables (merged with DB creds)
        image: Docker image to use
        timeout: Container timeout in seconds

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    import docker

    # Connect to Docker daemon
    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        logger.error(f"Docker not available: {e}")
        return (1, "", f"Docker not available: {e}")

    r_script_path = f"/app/r_scripts/{script_name}"
    host_project_path = os.environ.get("HOST_PROJECT_PATH", "/opt/dziki")
    r_scripts_host = f"{host_project_path}/r_scripts"

    # Build environment: DB creds + caller extras
    env = {**_build_db_env(), **(extra_env or {})}

    logger.info(f"Running R script via Docker: {script_name}")

    try:
        container_output = client.containers.run(
            image,
            command=["Rscript", "--vanilla", r_script_path],
            environment=env,
            network=DOCKER_NETWORK,
            volumes={
                "dziki_r_data": {"bind": "/app/data", "mode": "rw"},
                r_scripts_host: {"bind": "/app/r_scripts", "mode": "ro"},
            },
            remove=True,
            detach=False,
            stdout=True,
            stderr=True,
            mem_limit="4g",
        )

        output = (
            container_output.decode("utf-8")
            if isinstance(container_output, bytes)
            else str(container_output)
        )
        logger.info(f"R script completed successfully: {script_name}")
        return (0, output, "")
