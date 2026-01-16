"""
Research Pipeline Orchestrator.

Executes the Research Pipeline step-by-step with proper error handling.
Each step is logged to ResearchStepLog. The pipeline stops on first failure.

Exit code conventions (shared with R scripts):
    0   - success
    1   - validation / input error (do not retry)
    2   - timeout (stop pipeline)
    3   - computation error / fallback (stop pipeline)
    137 - OOM killed by kernel
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

    except docker.errors.ContainerError as e:
        stderr = e.stderr.decode("utf-8")[:2000] if e.stderr else str(e)
        exit_code = e.exit_status if hasattr(e, "exit_status") else 1
        logger.error(
            f"R script failed: {script_name} (exit={exit_code}), stderr: {stderr[:200]}"
        )
        return (exit_code, "", stderr)

    except docker.errors.ImageNotFound:
        msg = f"Docker image not found: {image}"
        logger.error(msg)
        return (1, "", msg)

    except Exception as e:
        logger.exception(f"Docker error running {script_name}: {e}")
        return (1, "", str(e))


# ORCHESTRATOR


class ResearchOrchestrator:
    """
    Executes the Research Pipeline with per-step logging and fail-fast semantics.

    Usage:
        config = ResearchConfig.objects.get(is_active=True)
        orch = ResearchOrchestrator(config)
        run = orch.execute()
        # run.status == 'success' or 'failed'
    """

    # Mapping geometry_type -> target table
    GEOMETRY_TABLE_MAP = {
        "voronoi": "sightings_gridcell_research",
        "grid_500": "research_grid_500m",
    }

    def __init__(self, config: ResearchConfig, run: Optional[ResearchRun] = None):
        self.config = config
        self.run: Optional[ResearchRun] = run  # Can be pre-created by views_research
        self._env: dict = {}
        # WebSocket channel layer for progress updates
        self._channel_layer = get_channel_layer() if CHANNELS_AVAILABLE else None
        self._group_name: Optional[str] = None

    def _emit_progress(self, event: str, **kwargs):
        """
        Emit a progress update to connected WebSocket clients.

        Args:
            event: Event type (pipeline_start, step_start, step_complete, pipeline_complete)
            **kwargs: Additional event data
        """
        if not self._channel_layer or not self._group_name:
            return

        try:
            async_to_sync(self._channel_layer.group_send)(
                self._group_name,
                {
                    "type": "progress.update",
                    "data": {
                        "event": event,
                        "timestamp": timezone.now().isoformat(),
                        **kwargs,
                    },
                },
            )
        except Exception as e:
            logger.warning(f"Failed to emit progress event '{event}': {e}")

    def _get_target_table(self) -> str:
        """
        Return the appropriate target table based on geometry_type.

        Mapping:
            voronoi  -> sightings_gridcell_research
            grid_500 -> research_grid_500m
        """
        geometry_type = getattr(self.config, "geometry_type", "voronoi")
        table = self.GEOMETRY_TABLE_MAP.get(
            geometry_type, "sightings_gridcell_research"
        )
        logger.info(f"Target table for geometry_type={geometry_type}: {table}")
        return table

    def execute(self) -> ResearchRun:
        """
        Run the full pipeline. Returns the ResearchRun with final status.

        Guarantees:
        - Every step gets a ResearchStepLog (even if skipped)
        - Pipeline stops on first failure (PipelineError)
        - run.status is always set to 'success' or 'failed'
        - run.error_message is set on failure
        """
        # 1. Use pre-created run or create new one
        if self.run is None:
            # Legacy path: create run here (for direct orchestrator usage)
            self.run = ResearchRun.objects.create(
                config=self.config,
                config_snapshot=self._snapshot_config(),
                status=RunStatus.RUNNING,
                n_sightings=self._count_sightings(),
            )
        else:
            # Run was pre-created by views_research.run_pipeline()
            # Update status from PENDING to RUNNING
            self.run.status = RunStatus.RUNNING
            self.run.save(update_fields=["status"])

        # Set up WebSocket group for progress updates
        self._group_name = f"research_{self.run.id}"

        # Emit pipeline start event
        self._emit_progress(
            "pipeline_start",
            run_id=str(self.run.id),
            config_name=self.config.name,
            total_steps=len(PIPELINE_STEPS),
            n_sightings=self.run.n_sightings,
        )

        # 2. Build environment for R scripts
        self._env = self.config.to_env_dict()
        self._env["RESEARCH_RUN_ID"] = str(self.run.id)

        # CRITICAL: Route to the correct table based on geometry_type
        geometry_type = getattr(self.config, "geometry_type", "voronoi")
        target_table = self._get_target_table()
        self._env["RESEARCH_TARGET_TABLE"] = target_table
        self._env["RESEARCH_GEOMETRY_TYPE"] = geometry_type

        # Log pipeline start with key parameters
        logger.info("=" * 60)
        logger.info("=== RESEARCH PIPELINE START ===")
        logger.info(f"Run ID:        {self.run.id}")
        logger.info(f"Config:        {self.config.name}")
        logger.info(f"Geometry type: {geometry_type}")
        logger.info(f"Target table:  {target_table}")
        logger.info(f"Model type:    {getattr(self.config, 'model_type', 'auto')}")
        logger.info(f"Y formula:     {getattr(self.config, 'y_formula', 'log_pop')}")
        logger.info("=" * 60)

        try:
            # 3. Execute steps in order
            for order, step_def in enumerate(PIPELINE_STEPS, 1):
                # Emit step start event
                self._emit_progress(
                    "step_start",
                    step_number=order,
                    step_name=step_def["name"],
                    step_description=step_def.get("description", ""),
                    total_steps=len(PIPELINE_STEPS),
                )

                self._execute_step(order, step_def)

                # After step completion, emit step_complete event
                try:
                    step_log = ResearchStepLog.objects.get(
                        run=self.run, step_order=order
                    )
                    self._emit_progress(
                        "step_complete",
                        step_number=order,
                        step_name=step_def["name"],
                        status=step_log.status,
                        duration_seconds=step_log.duration_seconds,
                        exit_code=step_log.exit_code,
                        # Send stdout/stderr for live console view
                        stdout=step_log.stdout[-3000:] if step_log.stdout else None,
                        stderr=step_log.stderr[-1000:] if step_log.stderr else None,
                    )
                except ResearchStepLog.DoesNotExist:
                    pass

            # 4. All steps passed - fill n_cells from target table
            target_table = self._get_target_table()
            with connection.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {target_table}")  # noqa: S608 - table from allowlist
                self.run.n_cells = cur.fetchone()[0]

            self.run.status = RunStatus.SUCCESS
            self.run.finished_at = timezone.now()
            self.run.save(update_fields=["status", "finished_at", "n_cells"])

            # Emit pipeline complete event
            self._emit_progress(
                "pipeline_complete",
                status="success",
                total_duration_seconds=(
                    self.run.finished_at - self.run.started_at
                ).total_seconds()
                if self.run.started_at
                else None,
            )

            logger.info(f"Research pipeline completed: run={self.run.id}")

        except PipelineError as e:
            self.run.status = RunStatus.FAILED
            self.run.finished_at = timezone.now()
            self.run.error_message = f"[{e.step_name}] exit={e.exit_code}: {e}"
            self.run.save(update_fields=["status", "finished_at", "error_message"])

            # Emit pipeline failed event
            self._emit_progress(
                "pipeline_complete",
                status="failed",
                error_message=self.run.error_message,
                failed_step=e.step_name,
                exit_code=e.exit_code,
            )

            logger.error(f"Research pipeline FAILED at {e.step_name}: {e}")

        except Exception as e:
            self.run.status = RunStatus.FAILED
            self.run.finished_at = timezone.now()
            self.run.error_message = f"Unexpected: {e}"
            self.run.save(update_fields=["status", "finished_at", "error_message"])

            # Emit pipeline failed event
            self._emit_progress(
                "pipeline_complete",
                status="failed",
                error_message=self.run.error_message,
            )

            logger.exception(f"Research pipeline unexpected error: {e}")

        return self.run

    # Step execution

    def _execute_step(self, order: int, step_def: dict):
        """
        Execute a single pipeline step with full logging.

        Raises PipelineError if the step fails.
        """
        name = step_def["name"]
        step_type = step_def["type"]
        script = step_def.get("script")

        # Create log entry
        step_log = ResearchStepLog.objects.create(
            run=self.run,
            step_name=name,
            step_order=order,
            step_type=step_type,
            status=StepStatus.RUNNING,
            started_at=timezone.now(),
            input_params=self._env,
        )

        # Check if step has an implementation
        if step_type == StepType.R and not script:
            self._finish_step(step_log, StepStatus.SKIPPED)
            logger.info(
                f"Step {order}/{len(PIPELINE_STEPS)} [{name}]: SKIPPED (no script)"
            )
            return

        if step_type == StepType.PYTHON and not script:
            self._finish_step(step_log, StepStatus.SKIPPED)
            logger.info(
                f"Step {order}/{len(PIPELINE_STEPS)} [{name}]: SKIPPED (not implemented)"
            )
            return

        logger.info(f"Step {order}/{len(PIPELINE_STEPS)} [{name}]: starting...")

        # Dispatch by type
        try:
            if step_type == StepType.R:
                exit_code, stdout, stderr = run_r_script(
                    script_name=script,
                    extra_env=self._env,
                )
                self._handle_exit_code(step_log, name, exit_code, stdout, stderr)
            else:
                # Python steps - placeholder for future implementation
                self._finish_step(step_log, StepStatus.SKIPPED)
                return

        except PipelineError:
            raise  # re-raise to stop pipeline

        except Exception as e:
            self._finish_step(step_log, StepStatus.FAILED, exit_code=1, stderr=str(e))
            raise PipelineError(
                str(e),
                step_name=name,
                exit_code=1,
                stderr=str(e),
            )

    def _handle_exit_code(
        self,
        step_log: ResearchStepLog,
        step_name: str,
        exit_code: int,
        stdout: str,
        stderr: str,
    ):
        """
        Interpret R script exit code and update step log.

        Exit codes:
            0   - success
            1   - validation error (stop pipeline)
            2   - timeout (stop pipeline)
            3   - computation error / graceful degradation (stop pipeline)
            137 - OOM (stop pipeline)
        """
        if exit_code == 0:
            self._finish_step(
                step_log, StepStatus.SUCCESS, exit_code=0, stdout=stdout, stderr=stderr
            )
            logger.info(f"Step [{step_name}]: SUCCESS")
            return

        # Any non-zero code stops the pipeline
        self._finish_step(
            step_log,
            StepStatus.FAILED,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

        if exit_code == 2:
            msg = f"Timeout (exit=2): {stderr[:300]}"
        elif exit_code == 3:
            msg = f"Computation error / fallback (exit=3): {stderr[:300]}"
        elif exit_code == 137:
            msg = f"Out of memory (exit=137, OOM killed): {stderr[:300]}"
        else:
            msg = f"R script error (exit={exit_code}): {stderr[:300]}"

        raise PipelineError(
            msg,
            step_name=step_name,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    # Helpers

    def _finish_step(
        self,
        step_log: ResearchStepLog,
        status: str,
        exit_code: Optional[int] = None,
        stdout: str = "",
        stderr: str = "",
        output_stats: Optional[dict] = None,
    ):
        now = timezone.now()
        step_log.status = status
        step_log.finished_at = now
        step_log.exit_code = exit_code
        step_log.stdout = stdout[:50000]  # truncate to avoid DB bloat
        step_log.stderr = stderr[:50000]
        if output_stats:
            step_log.output_stats = output_stats
        if step_log.started_at:
            step_log.duration_seconds = (now - step_log.started_at).total_seconds()

        # Parse warnings and errors from R output
        warnings_found = []
        errors_found = []
        for line in stdout.split("\n"):
            line_lower = line.lower()
            if "warning" in line_lower or "warn:" in line_lower:
                warnings_found.append(line.strip())
            elif "error" in line_lower and "standard error" not in line_lower:
                errors_found.append(line.strip())

        # stderr often contains R warnings too
        if stderr:
            for line in stderr.split("\n"):
                line_stripped = line.strip()
                if line_stripped and line_stripped not in errors_found:
                    if "warning" in line.lower():
                        warnings_found.append(line_stripped)
                    else:
                        errors_found.append(line_stripped)

        if warnings_found:
            step_log.warnings = warnings_found[:50]  # max 50 warnings
        if errors_found and exit_code != 0:
            step_log.errors = errors_found[:20]  # max 20 errors

        step_log.save()

    def _snapshot_config(self) -> dict:
        """Serialize config to a JSON-safe dict for reproducibility."""
        c = self.config
        return {
            "name": c.name,
            "geometry_type": c.geometry_type,
            "population_method": c.population_method,
            "y_formula": c.y_formula,
            "w_method": c.w_method,
            "k_range_min": c.k_range_min,
            "k_range_max": c.k_range_max,
            "model_type": c.model_type,
            "active_predictors": c.active_predictors,
            "run_moran": c.run_moran,
            "run_lm_tests": c.run_lm_tests,
            "run_lisa": c.run_lisa,
            "run_eta": c.run_eta,
            "vif_threshold": c.vif_threshold,
            "alpha": c.alpha,
            "seed": c.seed,
            "date_from": c.date_from.isoformat() if c.date_from else None,
            "date_to": c.date_to.isoformat() if c.date_to else None,
        }

    def _count_sightings(self) -> int:
        """Count verified sightings, respecting temporal filter."""
        sql = "SELECT COUNT(*) FROM sightings_sighting WHERE status = 'verified'"
        params = []
        if self.config.date_from:
            sql += " AND observed_at >= %s"
            params.append(self.config.date_from)
        if self.config.date_to:
            sql += " AND observed_at <= %s"
            params.append(self.config.date_to)
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()[0]
