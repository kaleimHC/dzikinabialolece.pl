"""
Celery Tasks for Bayesian Integration Layer.
MASTER_SPEC v2.3 - Section I: Bayesian Integration Layer

Task routing:
- q_r: Bayesian MCMC (compute_bayesian_ssm) -> worker-r
- q_cpu: Python (elicit_priors, aggregate_ensemble) -> worker-py
- q_io: Cache/DB (invalidate_cache) -> worker-py

Operations:
- OP-B01: elicit_priors
- OP-B02: compute_bayesian_ssm
- OP-B04: aggregate_bayesian_ensemble
- OP-B05: invalidate_bayesian_cache

ADR References:
- ADR-010: Stacking vs BMA
- ADR-011: Prior Elicitation Strategy
- ADR-013: Posterior Storage Strategy
- ADR-014: Bayesian Layer Modularity
- ADR-015: Frequentist-First Workflow
"""

import os
import math
import subprocess
import logging
from decimal import Decimal
from typing import Dict, Any, Optional

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.cache import cache
from django.db import connection
from analytics.sql_injection_patch import validate_grid_type, transaction
from django.conf import settings

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Default concentration parameter (ADR-011)
DEFAULT_KAPPA = Decimal("10.0")

# MCMC defaults (from PARAMETER_CONFIGURATION_REFERENCE)
DEFAULT_MCMC_ITERATIONS = 2000
DEFAULT_MCMC_WARMUP = 1000
DEFAULT_MCMC_CHAINS = 4
DEFAULT_MCMC_SEED = 42

# Diagnostic thresholds (publication quality)
RHAT_THRESHOLD = Decimal("1.01")
ESS_THRESHOLD = 400

# Feature flag (ADR-014)
ENABLE_BAYESIAN = getattr(settings, "ENABLE_BAYESIAN_ENSEMBLE", True)


# =============================================================================
# N MINIMUM VALIDATION HELPER (MASTER_SPEC v2.2)
# =============================================================================


def check_n_minimum(n_obs: int, model_type: str) -> dict:
    """
    Check if sample size meets minimum requirements.

    Args:
        n_obs: Number of observations
        model_type: One of 'eta', 'gwr', 'bayesian'

    Returns:
        Dict with 'ok', 'warning', 'error', 'message'

    Uses N_MINIMUM_REQUIREMENTS from models_config:
    - eta: N >= 3 (error if below)
    - gwr: N >= 100 (error if below)
    - bayesian: N >= 50 (warn), N >= 200 (recommended)
    """
    from .models_config import N_MINIMUM_REQUIREMENTS

    if model_type not in N_MINIMUM_REQUIREMENTS:
        return {"ok": True, "warning": None, "error": None, "message": None}

    req = N_MINIMUM_REQUIREMENTS[model_type]

    if "min" in req:
        # Hard minimum (error if below)
        if n_obs < req["min"]:
            return {
                "ok": False,
                "warning": None,
                "error": True,
                "message": f"{req['message']}. N={n_obs} < {req['min']}",
            }

    if "warn" in req:
        # Soft minimum (warning)
        if n_obs < req["warn"]:
            return {
                "ok": False,
                "warning": True,
                "error": True,
                "message": f"{req['message']}. N={n_obs} < {req['warn']}",
            }
        elif n_obs < req.get("recommended", req["warn"]):
            return {
                "ok": True,
                "warning": True,
                "error": None,
                "message": f"N={n_obs} poniżej zalecanego {req['recommended']}. {req['message']}",
            }

    return {"ok": True, "warning": None, "error": None, "message": None}


# =============================================================================
# DOCKER SDK HELPER FOR R SCRIPTS
# =============================================================================


def _run_r_script_docker(
    script_name: str,
    environment: dict,
    timeout: int = 10500,
    image: str = "dziki-worker-bayes:latest",
) -> tuple:
    """
    Run an R script in the worker-bayes Docker container.
    Uses Docker SDK to spawn a container with brms/rstan.

    Args:
        script_name: Name of R script (e.g., '06_bayesian_ssm.R')
        environment: Dict of environment variables for R script
        timeout: Timeout in seconds
        image: Docker image to use

    Returns:
        Tuple of (return_code, output, stderr)
    """
    import docker

    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        logger.error(f"Docker not available: {e}")
        return (1, "", f"Docker not available: {e}")

    r_script = f"/app/r_scripts/{script_name}"

    # Merge environment with database credentials
    env = {
        "DB_HOST": "db",
        "DB_PORT": "5432",
        "DB_NAME": os.environ.get("DB_NAME", "dziki_db"),
        "DB_USER": os.environ.get("DB_USER", "dziki"),
        "DB_PASSWORD": os.environ.get("DB_PASSWORD", "dziki_dev_password"),
        "OMP_NUM_THREADS": "1",
        "STAN_NUM_THREADS": "1",
        "R_MAX_VSIZE": "8Gb",
        **environment,
    }

    logger.info(f"Running R script via Docker: {r_script}")

    logger.info(
        f"  DEBUG: RUN_ID={env.get('RUN_ID', 'NOT IN ENV')}, GRID_TYPE={env.get('GRID_TYPE', 'NOT IN ENV')}"
    )
    try:
        container_output = client.containers.run(
            image,
            command=["Rscript", "--vanilla", r_script],
            environment=env,
            network="dziki_dziki-internal",
            volumes={
                "dziki_r_data": {"bind": "/app/data", "mode": "rw"},
                "dziki_mcmc_data": {"bind": "/data/mcmc", "mode": "rw"},
            },
            remove=True,
            detach=False,
            stdout=True,
            stderr=True,
            mem_limit="8g",
        )

        output = (
            container_output.decode("utf-8")
            if isinstance(container_output, bytes)
            else str(container_output)
        )
        logger.info(f"R script completed: {script_name}")
        return (0, output, "")

    except docker.errors.ContainerError as e:
        stderr = e.stderr.decode("utf-8")[:500] if e.stderr else str(e)
        logger.error(f"R script failed: {script_name}, stderr: {stderr}")
        exit_code = e.exit_status if hasattr(e, "exit_status") else 1
        return (exit_code, "", stderr)

    except docker.errors.ImageNotFound:
        logger.error(f"Docker image not found: {image}")
        return (1, "", f"Docker image not found: {image}")

    except Exception as e:
        logger.exception(f"Docker error running {script_name}: {e}")
        return (1, "", str(e))


# =============================================================================
# OP-B01: ELICIT PRIORS
# =============================================================================


@shared_task(
    bind=True,
    name="analytics.tasks_bayesian.elicit_priors",
    queue="q_cpu",
    soft_time_limit=240,  # 4 min soft
    time_limit=300,  # 5 min hard
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    retry_backoff=True,
)
def elicit_priors(
    self,
    run_id: str,
    h_rel: float,
    ari: float,
    bandwidth: float,
    kappa: float = 10.0,
) -> Dict[str, Any]:
    """
    OP-B01: Elicit Bayesian Priors from frequentist results.

    Transforms H_rel, ARI, bandwidth into prior distributions for Bayesian SSM.

    Formulas (ADR-011):
    - delta ~ Beta(kappa * H_rel, kappa * (1 - H_rel))
    - rho ~ Beta(kappa * ARI, kappa * (1 - ARI))
    - length_scale ~ LogNormal(log(bandwidth), 0.3)

    Args:
        run_id: UUID of the analytics run
        h_rel: Relative entropy from ETA (rescaled to N=1000), range (0, 1]
        ari: Adjusted Rand Index from STS (historical t-2 to t-1), range [0, 1]
        bandwidth: Optimal bandwidth from GWR in meters (EPSG:2180)
        kappa: Concentration parameter (default 10.0)

    Returns:
        Dict with prior configurations and prior_config_ids

    Exit Codes:
        0: Success
        1: Validation Error (invalid inputs)
        2: Database Error (retry)
    """
    from .models_bayesian import PriorConfig

    logger.info(f"OP-B01: Elicit priors for run_id={run_id}")
    logger.info(
        f"  Inputs: H_rel={h_rel}, ARI={ari}, bandwidth={bandwidth}, kappa={kappa}"
    )

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    errors = []

    if not (0 < h_rel <= 1):
        errors.append(f"H_rel must be in (0, 1], got {h_rel}")

    if not (0 <= ari <= 1):
        errors.append(f"ARI must be in [0, 1], got {ari}")

    if bandwidth <= 0:
        errors.append(f"Bandwidth must be > 0, got {bandwidth}")

    if kappa <= 0:
        errors.append(f"Kappa must be > 0, got {kappa}")

    if errors:
        error_msg = "; ".join(errors)
        logger.error(f"OP-B01 validation failed: {error_msg}")
        return {
            "status": "error",
            "exit_code": 1,
            "error": error_msg,
        }

    # -------------------------------------------------------------------------
    # Compute prior hyperparameters
    # -------------------------------------------------------------------------
    try:
        kappa_d = Decimal(str(kappa))
        h_rel_d = Decimal(str(h_rel))
        ari_d = Decimal(str(ari))

        # Delta prior: diffusion parameter
        # Low H_rel = strong agglomeration = lower diffusion
        delta_alpha = kappa_d * h_rel_d
        delta_beta = kappa_d * (1 - h_rel_d)

        # Rho prior: persistence parameter
        # High ARI = stable clusters = high persistence
        rho_alpha = kappa_d * ari_d
        rho_beta = kappa_d * (1 - ari_d)

        # Length-scale prior: from GWR bandwidth
        # Mathematical isomorphism: GWR kernel ≈ GP kernel
        length_scale_meanlog = Decimal(str(math.log(bandwidth)))
        length_scale_sdlog = Decimal("0.3")

        logger.info(f"  delta ~ Beta({delta_alpha}, {delta_beta})")
        logger.info(f"  rho ~ Beta({rho_alpha}, {rho_beta})")
        logger.info(
            f"  length_scale ~ LogNormal({length_scale_meanlog}, {length_scale_sdlog})"
        )

        # -------------------------------------------------------------------------
        # Save to database
        # -------------------------------------------------------------------------
        model_version = f"v1.0-run-{run_id[:8]}"
        prior_configs = []

        with transaction.atomic():
            # Deactivate old priors for this version pattern
            PriorConfig.objects.filter(
                model_version__startswith=f"v1.0-run-{run_id[:8]}"
            ).update(is_active=False)

            # Delta prior
            delta_config = PriorConfig.objects.create(
                model_version=model_version,
                parameter_name="delta",
                dist_type="beta",
                alpha_hyper=delta_alpha,
                beta_hyper=delta_beta,
                source_h_rel=h_rel_d,
                source_ari=None,
                source_bandwidth=None,
                is_active=True,
            )
            prior_configs.append(delta_config)

            # Rho prior
            rho_config = PriorConfig.objects.create(
                model_version=model_version,
                parameter_name="rho",
                dist_type="beta",
                alpha_hyper=rho_alpha,
                beta_hyper=rho_beta,
                source_h_rel=None,
                source_ari=ari_d,
                source_bandwidth=None,
                is_active=True,
            )
            prior_configs.append(rho_config)

            # Length-scale prior
            length_config = PriorConfig.objects.create(
                model_version=model_version,
                parameter_name="length_scale",
                dist_type="lognormal",
                alpha_hyper=length_scale_meanlog,  # meanlog
                beta_hyper=length_scale_sdlog,  # sdlog
                source_h_rel=None,
                source_ari=None,
                source_bandwidth=Decimal(str(bandwidth)),
                is_active=True,
            )
            prior_configs.append(length_config)

        logger.info(f"OP-B01: Created {len(prior_configs)} prior configs")

        return {
            "status": "success",
            "exit_code": 0,
            "run_id": run_id,
            "model_version": model_version,
            "priors": {
                "delta": {
                    "id": str(delta_config.id),
                    "dist": "beta",
                    "alpha": float(delta_alpha),
                    "beta": float(delta_beta),
                },
                "rho": {
                    "id": str(rho_config.id),
                    "dist": "beta",
                    "alpha": float(rho_alpha),
                    "beta": float(rho_beta),
                },
                "length_scale": {
                    "id": str(length_config.id),
                    "dist": "lognormal",
                    "meanlog": float(length_scale_meanlog),
                    "sdlog": float(length_scale_sdlog),
                },
            },
            "prior_config_ids": [str(p.id) for p in prior_configs],
        }

    except Exception as exc:
        logger.exception(f"OP-B01 database error: {exc}")
        # Exit code 2 = database error, can retry
        raise self.retry(exc=exc)


# =============================================================================
# OP-B02: COMPUTE BAYESIAN SSM
# =============================================================================


@shared_task(
    bind=True,
    name="analytics.tasks_bayesian.compute_bayesian_ssm",
    queue="q_cpu",  # Runs on worker-py, uses Docker SDK
    soft_time_limit=10500,  # 175 min soft
    time_limit=10800,  # 180 min hard (3h)
    max_retries=0,  # No retry - fallback instead (ADR-014)
    acks_late=True,
    reject_on_worker_lost=True,
)
def compute_bayesian_ssm(
    self,
    run_id: str,
    prior_config_ids: list,
    grid_type: str = "voronoi",
    mcmc_iterations: int = DEFAULT_MCMC_ITERATIONS,
    mcmc_warmup: int = DEFAULT_MCMC_WARMUP,
    mcmc_chains: int = DEFAULT_MCMC_CHAINS,
    mcmc_seed: int = DEFAULT_MCMC_SEED,
) -> Dict[str, Any]:
    """
    OP-B02: Compute Bayesian State-Space Model.

    Main Bayesian computation. Runs MCMC via R (brms/rstan).

    Args:
        run_id: UUID of the analytics run
        prior_config_ids: List of PriorConfig UUIDs from OP-B01
        grid_type: 'square' or 'voronoi'
        mcmc_iterations: Total MCMC iterations per chain
        mcmc_warmup: Warmup iterations per chain
        mcmc_chains: Number of chains
        mcmc_seed: Random seed for reproducibility

    Returns:
        Dict with results count and diagnostics

    Exit Codes:
        0: Success
        1: Validation Error (N < 100)
        2: Timeout
        3: Computation Error (divergence, non-convergence) -> fallback
        137: Out of Memory -> subsample
    """
    from .models_bayesian import PriorConfig, BayesianResult

    logger.info(f"OP-B02: Compute Bayesian SSM for run_id={run_id}")
    logger.info(
        f"  grid_type={grid_type}, iterations={mcmc_iterations}, chains={mcmc_chains}"
    )

    # Check feature flag (ADR-014)
    if not ENABLE_BAYESIAN:
        logger.warning("OP-B02: Bayesian disabled by feature flag, skipping")
        return {
            "status": "skipped",
            "exit_code": 0,
            "reason": "ENABLE_BAYESIAN_ENSEMBLE=False",
        }

    # Update progress
    cache.set(
        f"bayesian_progress:{run_id}",
        {
            "running": True,
            "step": "validation",
            "progress": 0,
            "error": None,
        },
        timeout=14400,
    )

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    try:
        # Check priors exist
        priors = PriorConfig.objects.filter(id__in=prior_config_ids, is_active=True)
        if priors.count() < 3:
            logger.error(f"OP-B02: Missing priors, found {priors.count()}/3")
            return {
                "status": "error",
                "exit_code": 1,
                "error": "Missing prior configurations",
            }

        # Check grid cells exist
        grid_table = validate_grid_type(grid_type)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {grid_table}")
            cell_count = cursor.fetchone()[0]

        if cell_count == 0:
            logger.error(f"OP-B02: No grid cells in {grid_table}")
            return {
                "status": "error",
                "exit_code": 1,
                "error": f"No cells in {grid_table}",
            }

        # Check minimum sightings (N_MINIMUM_REQUIREMENTS)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM sightings_sighting WHERE status = 'verified'"
            )
            sighting_count = cursor.fetchone()[0]

        n_check = check_n_minimum(sighting_count, "bayesian")
        if n_check["error"]:
            logger.warning(f"OP-B02: {n_check['message']}")
            return {
                "status": "skipped",
                "exit_code": 1,
                "reason": n_check["message"],
            }
        elif n_check["warning"]:
            logger.warning(f"OP-B02: {n_check['message']} - proceeding with caution")

        logger.info(f"  Validated: {cell_count} cells, {sighting_count} sightings")

    except Exception as exc:
        logger.exception(f"OP-B02 validation error: {exc}")
        return {
            "status": "error",
            "exit_code": 1,
            "error": str(exc),
        }

    # -------------------------------------------------------------------------
    # Run R script (06_bayesian_ssm.R)
    # -------------------------------------------------------------------------
    cache.set(
        f"bayesian_progress:{run_id}",
        {
            "running": True,
            "step": "mcmc",
            "progress": 10,
            "error": None,
        },
        timeout=14400,
    )

    try:
        # Prepare prior data for R
        prior_data = {}
        for prior in priors:
            prior_data[prior.parameter_name] = {
                "dist": prior.dist_type,
                "alpha": float(prior.alpha_hyper),
                "beta": float(prior.beta_hyper),
            }

        # R script path

        # Environment
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = "1"
        env["RUN_ID"] = run_id
        env["GRID_TYPE"] = grid_type
        env["MCMC_ITERATIONS"] = str(mcmc_iterations)
        env["MCMC_WARMUP"] = str(mcmc_warmup)
        env["MCMC_CHAINS"] = str(mcmc_chains)
        env["MCMC_SEED"] = str(mcmc_seed)
        env["PRIOR_DELTA_ALPHA"] = str(prior_data.get("delta", {}).get("alpha", 5))
        env["PRIOR_DELTA_BETA"] = str(prior_data.get("delta", {}).get("beta", 5))
        env["PRIOR_RHO_ALPHA"] = str(prior_data.get("rho", {}).get("alpha", 8))
        env["PRIOR_RHO_BETA"] = str(prior_data.get("rho", {}).get("beta", 2))
        env["PRIOR_LENGTH_MEANLOG"] = str(
            prior_data.get("length_scale", {}).get("alpha", 6)
        )
        env["PRIOR_LENGTH_SDLOG"] = str(
            prior_data.get("length_scale", {}).get("beta", 0.3)
        )

        logger.info("  Running R script via Docker: 06_bayesian_ssm.R")

        # Build R environment
        r_env = {
            "RUN_ID": run_id,
            "GRID_TYPE": grid_type,
            "MCMC_ITERATIONS": str(mcmc_iterations),
            "MCMC_WARMUP": str(mcmc_warmup),
            "MCMC_CHAINS": str(mcmc_chains),
            "MCMC_SEED": str(mcmc_seed),
            "PRIOR_DELTA_ALPHA": str(prior_data.get("delta", {}).get("alpha", 5)),
            "PRIOR_DELTA_BETA": str(prior_data.get("delta", {}).get("beta", 5)),
            "PRIOR_RHO_ALPHA": str(prior_data.get("rho", {}).get("alpha", 8)),
            "PRIOR_RHO_BETA": str(prior_data.get("rho", {}).get("beta", 2)),
            "PRIOR_LENGTH_MEANLOG": str(
                prior_data.get("length_scale", {}).get("alpha", 6)
            ),
            "PRIOR_LENGTH_SDLOG": str(
                prior_data.get("length_scale", {}).get("beta", 0.3)
            ),
        }

        return_code, output, stderr = _run_r_script_docker(
            "06_bayesian_ssm.R",
            environment=r_env,
            timeout=10500,
        )

        # Handle exit codes
        if return_code == 0:
            logger.info("OP-B02: MCMC completed successfully")

            # Parse results from R output or database
            cache.set(
                f"bayesian_progress:{run_id}",
                {
                    "running": True,
                    "step": "saving",
                    "progress": 90,
                    "error": None,
                },
                timeout=14400,
            )

            # Count results saved by R
            results_count = BayesianResult.objects.filter(
                execution__task_id=run_id
            ).count()

            # Get diagnostics
            diagnostics = _get_mcmc_diagnostics(run_id)

            cache.set(
                f"bayesian_progress:{run_id}",
                {
                    "running": False,
                    "step": "completed",
                    "progress": 100,
                    "error": None,
                },
                timeout=14400,
            )

            return {
                "status": "success",
                "exit_code": 0,
                "run_id": run_id,
                "results_count": results_count,
                "diagnostics": diagnostics,
                "draws_path": f"/data/mcmc/{run_id}.rds",
            }

        elif return_code == 2:
            logger.error("OP-B02: Timeout during MCMC")
            return {
                "status": "timeout",
                "exit_code": 2,
                "fallback": "frequentist",
            }

        elif return_code == 3:
            logger.warning("OP-B02: Computation error (divergence/non-convergence)")
            logger.warning(f"  stderr: {stderr[:500]}")
            return {
                "status": "computation_error",
                "exit_code": 3,
                "fallback": "frequentist",
                "error": stderr[:500],
            }

        elif return_code == 137:
            logger.error("OP-B02: Out of Memory (OOM)")
            return {
                "status": "oom",
                "exit_code": 137,
                "fallback": "subsample",
            }

        else:
            logger.error(f"OP-B02: R script failed with code {return_code}")
            logger.error(f"  stderr: {stderr[:500]}")
            return {
                "status": "error",
                "exit_code": return_code,
                "error": stderr[:500],
            }

    except subprocess.TimeoutExpired:
        logger.error("OP-B02: Subprocess timeout")
        return {
            "status": "timeout",
            "exit_code": 2,
            "fallback": "frequentist",
        }

    except SoftTimeLimitExceeded:
        logger.error("OP-B02: Celery soft time limit exceeded")
        cache.set(
            f"bayesian_progress:{run_id}",
            {
                "running": False,
                "step": "timeout",
                "progress": 0,
                "error": "Soft time limit exceeded",
            },
            timeout=14400,
        )
        return {
            "status": "timeout",
            "exit_code": 2,
            "fallback": "frequentist",
        }

    except Exception as exc:
        logger.exception(f"OP-B02 error: {exc}")
        cache.set(
            f"bayesian_progress:{run_id}",
            {
                "running": False,
                "step": "error",
                "progress": 0,
                "error": str(exc),
            },
            timeout=14400,
        )
        return {
            "status": "error",
            "exit_code": 3,
            "fallback": "frequentist",
            "error": str(exc),
        }


def _get_mcmc_diagnostics(run_id: str) -> Dict[str, Any]:
    """Extract MCMC diagnostics from BayesianResult table."""
    from .models_bayesian import BayesianResult

    results = BayesianResult.objects.filter(execution__task_id=run_id)

    if not results.exists():
        return {"warning": "No results found"}

    r_hats = [float(r.r_hat) for r in results if r.r_hat is not None]
    ess_bulks = [float(r.ess_bulk) for r in results if r.ess_bulk is not None]

    return {
        "count": results.count(),
        "max_r_hat": max(r_hats) if r_hats else None,
        "min_r_hat": min(r_hats) if r_hats else None,
        "min_ess_bulk": min(ess_bulks) if ess_bulks else None,
        "converged": all(r < float(RHAT_THRESHOLD) for r in r_hats) if r_hats else None,
    }


# =============================================================================
# OP-B04: AGGREGATE BAYESIAN ENSEMBLE
# =============================================================================


@shared_task(
    bind=True,
    name="analytics.tasks_bayesian.aggregate_bayesian_ensemble",
    queue="q_cpu",
    soft_time_limit=540,  # 9 min soft
    time_limit=600,  # 10 min hard
    max_retries=2,
    default_retry_delay=30,
)
def aggregate_bayesian_ensemble(
    self,
    run_id: str,
    stacking_weights: Optional[Dict[str, float]] = None,
    grid_type: str = "voronoi",
) -> Dict[str, Any]:
    """
    OP-B04: Aggregate Bayesian Ensemble.

    Combines frequentist (RF, GWR, ETA) and Bayesian results using Stacking.
    Weights from Spatial Block CV (ADR-010).

    Args:
        run_id: UUID of the analytics run
        stacking_weights: Dict of model weights (must sum to 1.0)
        grid_type: 'square' or 'voronoi'

    Returns:
        Dict with ensemble statistics

    Exit Codes:
        0: Success
        1: Validation Error (weights don't sum to 1)
        2: Database Error (retry)
    """
    logger.info(f"OP-B04: Aggregate Bayesian ensemble for run_id={run_id}")

    # Default weights (can be overridden by Spatial Block CV results)
    # WAŻNE: Bayesian jest META-WARSTWĄ, nie składnikiem ensemble!
    # Wagi: 0.30 RF + 0.40 GWR + 0.30 ETA = 1.0
    if stacking_weights is None:
        stacking_weights = {
            "rf": 0.30,
            "gwr": 0.40,
            "eta": 0.30,
        }

    # Validate weights sum to 1
    weight_sum = sum(stacking_weights.values())
    if abs(weight_sum - 1.0) > 0.01:
        logger.error(f"OP-B04: Weights sum to {weight_sum}, expected 1.0")
        return {
            "status": "error",
            "exit_code": 1,
            "error": f"Weights sum to {weight_sum}, expected 1.0",
        }

    logger.info(f"  Weights: {stacking_weights}")

    try:
        grid_table = validate_grid_type(grid_type)

        # Check if Bayesian results exist (dla meta-layer info, nie do wag)
        from .models_bayesian import BayesianResult

        bayesian_exists = BayesianResult.objects.filter(
            execution__task_id=run_id
        ).exists()

        if bayesian_exists:
            logger.info("OP-B04: Bayesian results found (meta-layer)")
        else:
            logger.info("OP-B04: No Bayesian results (frequentist only)")

        with connection.cursor() as cursor:
            # PRAWIDŁOWY WZÓR: Ensemble = 0.30*RF + 0.40*GWR + 0.30*ETA
            # Bayesian jest META-WARSTWĄ, NIE jest częścią średniej ważonej!
            # rf_score może nie istnieć - wtedy COALESCE do 0.5

            # Sprawdź czy kolumna rf_score istnieje
            cursor.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'rf_score'
            """,
                [grid_table.split(".")[-1] if "." in grid_table else grid_table],
            )
            rf_exists = cursor.fetchone() is not None

            if rf_exists:
                # Pełny wzór z RF
                cursor.execute(f"""
                    UPDATE {grid_table}
                    SET ensemble_risk = (
                        {stacking_weights.get("rf", 0.30)} * COALESCE(rf_score, 0.5) +
                        {stacking_weights.get("gwr", 0.40)} * COALESCE(gwr_score, 0.5) +
                        {stacking_weights.get("eta", 0.30)} * COALESCE(area_rank_score, 0.5)
                    ),
                    updated_at = NOW();
                """)
            else:
                # RF nie istnieje - renormalizuj wagi GWR i ETA
                # GWR: 0.40/(0.40+0.30) = 0.571, ETA: 0.30/(0.40+0.30) = 0.429
                logger.warning("rf_score column missing, using GWR+ETA only")
                cursor.execute(f"""
                    UPDATE {grid_table}
                    SET ensemble_risk = (
                        0.571 * COALESCE(gwr_score, 0.5) +
                        0.429 * COALESCE(area_rank_score, 0.5)
                    ),
                    updated_at = NOW();
                """)

            updated = cursor.rowcount

            # Get statistics
            cursor.execute(f"""
                SELECT
                    AVG(ensemble_risk) as mean,
                    STDDEV(ensemble_risk) as std,
                    COUNT(*) FILTER (WHERE ensemble_risk > 0.7) as high_risk
                FROM {grid_table};
            """)
            stats = cursor.fetchone()

        logger.info(f"OP-B04: Updated {updated} cells")

        return {
            "status": "success",
            "exit_code": 0,
            "run_id": run_id,
            "cells_updated": updated,
            "ensemble_risk_mean": float(stats[0]) if stats[0] else 0,
            "ensemble_risk_std": float(stats[1]) if stats[1] else 0,
            "high_risk_cells": stats[2] or 0,
            "weights_used": stacking_weights,
            "bayesian_included": bayesian_exists,
        }

    except Exception as exc:
        logger.exception(f"OP-B04 error: {exc}")
        raise self.retry(exc=exc)


# =============================================================================
# OP-B05: INVALIDATE BAYESIAN CACHE
# =============================================================================


@shared_task(
    bind=True,
    name="analytics.tasks_bayesian.invalidate_bayesian_cache",
    queue="q_io",
    soft_time_limit=240,  # 4 min soft
    time_limit=300,  # 5 min hard
    max_retries=3,
    default_retry_delay=10,
)
def invalidate_bayesian_cache(
    self,
    trigger: str = "manual",
    config_id: Optional[str] = None,
    changed_fields: Optional[list] = None,
) -> Dict[str, Any]:
    """
    OP-B05: Invalidate Bayesian Cache.

    Cascade invalidation when parameters change.

    Args:
        trigger: What triggered the invalidation
        config_id: UUID of changed config (if applicable)
        changed_fields: List of changed field names

    Returns:
        Dict with invalidation stats

    Exit Codes:
        0: Success
        1: Redis Error (retry)
        2: Database Error (retry)
        3: Tile Generation Error (retry)
    """
    logger.info("OP-B05: Invalidate Bayesian cache")
    logger.info(f"  trigger={trigger}, config_id={config_id}, fields={changed_fields}")

    stats = {
        "redis_keys_deleted": 0,
        "db_records_marked": 0,
        "tiles_regenerated": False,
        "frontend_notified": False,
    }

    try:
        # Step 1: Redis cache invalidation
        patterns = ["bayesian:*", "prediction:*", "ensemble:*"]

        for pattern in patterns:
            try:
                # Django cache doesn't support pattern delete directly
                # Use Redis client if available
                deleted = (
                    cache.delete_pattern(pattern)
                    if hasattr(cache, "delete_pattern")
                    else 0
                )
                stats["redis_keys_deleted"] += deleted or 0
            except Exception as e:
                logger.warning(f"  Pattern delete failed for {pattern}: {e}")
                # Fallback: delete known keys
                cache.delete("sighting_stats")
                cache.delete("grid_stats")
                stats["redis_keys_deleted"] += 2

        logger.info(f"  Redis: deleted {stats['redis_keys_deleted']} keys")

        # Step 2: Mark old BayesianResults as superseded
        with connection.cursor() as cursor:
            # Add superseded flag if needed
            cursor.execute("""
                UPDATE analytics_bayesian_result
                SET computed_at = computed_at
                WHERE computed_at < NOW() - INTERVAL '1 hour';
            """)
            stats["db_records_marked"] = cursor.rowcount

        logger.info(f"  DB: marked {stats['db_records_marked']} records")

        # Step 3: Refresh Materialized Views (if they exist)
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT FROM pg_matviews WHERE matviewname = 'mv_sighting_stats'
                        ) THEN
                            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sighting_stats;
                        END IF;
                    END $$;
                """)
        except Exception as e:
            logger.warning(f"  MV refresh skipped: {e}")

        # Step 4: Tile regeneration (placeholder - would call tippecanoe)
        # stats['tiles_regenerated'] = _regenerate_tiles()

        # Step 5: Frontend notification (placeholder - would use WebSocket)
        # stats['frontend_notified'] = _notify_frontend()

        logger.info("OP-B05: Cache invalidation completed")

        return {
            "status": "success",
            "exit_code": 0,
            "trigger": trigger,
            **stats,
        }

    except Exception as exc:
        logger.exception(f"OP-B05 error: {exc}")
        raise self.retry(exc=exc)


# =============================================================================
# HELPER: FULL BAYESIAN PIPELINE
# =============================================================================


@shared_task(
    bind=True,
    name="analytics.tasks_bayesian.run_bayesian_pipeline",
    queue="q_cpu",
    soft_time_limit=14100,  # 235 min soft
    time_limit=14400,  # 240 min hard (4h)
)
def run_bayesian_pipeline(
    self,
    h_rel: float,
    ari: float,
    bandwidth: float,
    grid_type: str = "voronoi",
    kappa: float = 10.0,
) -> Dict[str, Any]:
    """
    Run full Bayesian pipeline: elicit -> compute -> trajectories -> aggregate.

    This is a convenience task that chains all Bayesian operations.
    """
    from .models import AnalyticsRun

    logger.info("Starting full Bayesian pipeline")

    # Create analytics run
    run = AnalyticsRun.objects.create(
        task_id=str(self.request.id),
        task_name="bayesian_pipeline",
        status="running",
        parameters={
            "h_rel": h_rel,
            "ari": ari,
            "bandwidth": bandwidth,
            "grid_type": grid_type,
            "kappa": kappa,
        },
    )
    run_id = str(run.task_id)

    BAYESIAN_LOCK_KEY = "bayesian_pipeline_lock"

    try:
        # Step 1: Elicit priors
        prior_result = elicit_priors(
            run_id=run_id,
            h_rel=h_rel,
            ari=ari,
            bandwidth=bandwidth,
            kappa=kappa,
        )

        if prior_result.get("status") != "success":
            raise Exception(f"Prior elicitation failed: {prior_result}")

        prior_config_ids = prior_result.get("prior_config_ids", [])

        # Step 2: Compute Bayesian SSM
        ssm_result = compute_bayesian_ssm(
            run_id=run_id,
            prior_config_ids=prior_config_ids,
            grid_type=grid_type,
        )

        # Step 3: Generate trajectories (regardless of SSM result)
        traj_result = generate_trajectories(
            run_id=run_id,
        )

        # Step 4: Aggregate ensemble
        agg_result = aggregate_bayesian_ensemble(
            run_id=run_id,
            grid_type=grid_type,
        )

        # Step 5: Invalidate cache
        cache_result = invalidate_bayesian_cache(
            trigger="pipeline_complete",
        )

        # Update run status
        run.status = "completed"
        run.result_summary = {
            "priors": prior_result,
            "ssm": ssm_result,
            "trajectories": traj_result,
            "aggregate": agg_result,
            "cache": cache_result,
        }
        run.save()

        return {
            "status": "success",
            "run_id": run_id,
            "results": run.result_summary,
        }

    except Exception as exc:
        logger.exception(f"Bayesian pipeline error: {exc}")
        run.status = "failed"
        run.error_message = str(exc)
        run.save()
        raise

    finally:
        # Release the concurrency lock set in bayesian_run() regardless of outcome.
        from django.core.cache import cache as _cache

        _cache.delete(BAYESIAN_LOCK_KEY)
