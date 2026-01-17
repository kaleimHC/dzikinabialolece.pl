"""
Celery Task for Research Pipeline (spatialWarsaw).

Wraps ResearchOrchestrator.execute() to run asynchronously.
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    queue="q_cpu",
    soft_time_limit=60,  # 1 min soft
    time_limit=120,  # 2 min hard
    max_retries=0,
)
def run_preview_pipeline(self, geometry_type: str, target_table: str):
    from .orchestrator_research import run_r_script

    env = {
        "RESEARCH_GEOMETRY_TYPE": geometry_type,
        "RESEARCH_TARGET_TABLE": target_table,
    }

    logger.info(f"[Celery] run_preview_pipeline: geometry_type={geometry_type}")

    exit_code, stdout, stderr = run_r_script("01_generate_voronoi.R", extra_env=env)
    if exit_code != 0:
        logger.error(f"[Celery] Geometry generation failed: {stderr[:500]}")
        return {
            "status": "error",
            "step": "geometry",
            "exit_code": exit_code,
            "stderr": stderr[:500],
        }

    exit_code, stdout, stderr = run_r_script(
        "research/03_osm_features.R", extra_env=env
    )
    if exit_code != 0:
        logger.error(f"[Celery] OSM features failed: {stderr[:500]}")
        return {
            "status": "error",
            "step": "osm_features",
            "exit_code": exit_code,
            "stderr": stderr[:500],
        }

    logger.info(f"[Celery] run_preview_pipeline complete for {geometry_type}")
    return {
        "status": "success",
        "geometry_type": geometry_type,
    }


@shared_task(
    bind=True,
    queue="q_cpu",
    soft_time_limit=300,  # 5 min soft
    time_limit=360,  # 6 min hard
    max_retries=0,
)
def run_research_pipeline(self, run_id: str):
    from .orchestrator_research import ResearchOrchestrator
    from .models_research import ResearchRun

    logger.info(f"[Celery] Starting research pipeline for run_id={run_id}")

    try:
        run = ResearchRun.objects.select_related("config").get(pk=run_id)
    except ResearchRun.DoesNotExist:
        logger.error(f"[Celery] ResearchRun {run_id} not found")
        return {
            "status": "error",
            "error": f"Run {run_id} not found",
        }

    if not run.config:
        logger.error(f"[Celery] ResearchRun {run_id} has no config")
        return {
            "status": "error",
            "error": f"Run {run_id} has no associated config",
        }

    try:
        orchestrator = ResearchOrchestrator(run.config, run=run)
        result = orchestrator.execute()

        logger.info(
            f"[Celery] Research pipeline completed: run_id={result.id}, status={result.status}"
        )

        return {
            "run_id": str(result.id),
            "status": result.status,
            "config_name": run.config.name,
            "n_cells": result.n_cells,
            "error": result.error_message,
        }

    except Exception as e:
        logger.exception(f"[Celery] Research pipeline failed: {e}")
        run.status = "failed"
        run.error_message = str(e)
        run.save(update_fields=["status", "error_message"])
        return {
            "status": "error",
            "run_id": str(run.id),
            "error": str(e),
        }
