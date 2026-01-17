"""
API views for Research Pipeline.

Endpoints:
    /api/research/configs/              GET, POST
    /api/research/configs/{id}/         GET, PUT
    /api/research/configs/{id}/activate/ POST
    /api/research/run/                  POST
    /api/research/runs/                 GET
    /api/research/runs/{id}/            GET
    /api/research/runs/{id}/steps/      GET
    /api/research/runs/{id}/diagnostics/ GET
    /api/research/status/               GET
"""

import logging

from django.db import connection
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .permissions import PipelineRunThrottle
from .sql_injection_patch import validate_geometry_type
from .models_research import (
    ResearchConfig,
    ResearchRun,
    ResearchStepLog,
    ResearchDiagnostics,
    ALL_PREDICTORS,
)

logger = logging.getLogger(__name__)


# SERIALIZERS (dict-based, matching existing project style)


def _serialize_config(c: ResearchConfig) -> dict:
    return {
        "id": c.pk,
        "name": c.name,
        "is_active": c.is_active,
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
        # Regime model fields
        "use_regime_model": c.use_regime_model,
        "regime_type": c.regime_type,
        "regime_threshold": c.regime_threshold,
        "regime_threshold_urban": c.regime_threshold_urban,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _serialize_run(r: ResearchRun) -> dict:
    return {
        "id": str(r.id),
        "config_name": r.config.name if r.config else None,
        "config_id": r.config_id,
        "status": r.status,
        "n_sightings": r.n_sightings,
        "n_cells": r.n_cells,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "error_message": r.error_message or None,
    }


def _serialize_run_detail(r: ResearchRun) -> dict:
    data = _serialize_run(r)
    data["config_snapshot"] = r.config_snapshot
    return data


def _serialize_step(s: ResearchStepLog) -> dict:
    return {
        "step_order": s.step_order,
        "step_name": s.step_name,
        "step_type": s.step_type,
        "status": s.status,
        "exit_code": s.exit_code,
        "duration_seconds": s.duration_seconds,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "finished_at": s.finished_at.isoformat() if s.finished_at else None,
        "stdout": s.stdout[:500] if s.stdout else None,
        "stderr": s.stderr[:500] if s.stderr else None,
        "output_stats": s.output_stats,
        "errors": s.errors,
        "warnings": s.warnings,
    }


def _serialize_diagnostics(d: ResearchDiagnostics) -> dict:
    return {
        "moran": {
            "i": d.moran_i,
            "expected": d.moran_expected,
            "variance": d.moran_variance,
            "z": d.moran_z,
            "p": d.moran_p,
        },
        "lm_tests": {
            "lm_lag": {"stat": d.lm_lag_stat, "p": d.lm_lag_p},
            "lm_error": {"stat": d.lm_error_stat, "p": d.lm_error_p},
            "rlm_lag": {"stat": d.rlm_lag_stat, "p": d.rlm_lag_p},
            "rlm_error": {"stat": d.rlm_error_stat, "p": d.rlm_error_p},
        },
        "model": {
            "selected": d.model_selected,
            "aic": d.aic,
            "log_likelihood": d.log_likelihood,
            "r_squared": d.r_squared,
            "rho": d.rho,
            "lambda": d.lambda_param,
            "coefficients": d.coefficients,
        },
        "lisa": {
            "hh": d.lisa_hh_count,
            "ll": d.lisa_ll_count,
            "hl": d.lisa_hl_count,
            "lh": d.lisa_lh_count,
            "ns": d.lisa_ns_count,
        },
        "vif": {
            "results": d.vif_results,
            "dropped": d.predictors_dropped,
        },
        "eta": {
            "h_emp": d.eta_h_emp,
            "h_max": d.eta_h_max,
            "h_rel": d.eta_h_rel,
        },
        "w_metrics": {
            "k_selected": d.k_selected,
            "mean_neighbors": d.mean_neighbors,
        },
        # Impacts (SAR/SDM only) - LeSage & Pace (2009)
        # For SAR/SDM, β coefficients need spatial multiplier correction
        "impacts": d.impacts,
    }


# CONFIG FIELDS — accepted from request body

_CONFIG_WRITABLE_FIELDS = {
    "name": str,
    "geometry_type": str,
    "population_method": str,
    "y_formula": str,
    "w_method": str,
    "k_range_min": int,
    "k_range_max": int,
    "model_type": str,
    "active_predictors": list,
    "run_moran": bool,
    "run_lm_tests": bool,
    "run_lisa": bool,
    "run_eta": bool,
    "vif_threshold": float,
    "alpha": float,
    "seed": int,
    "date_from": str,
    "date_to": str,
    # Regime model fields
    "use_regime_model": bool,
    "regime_type": str,
    "regime_threshold": float,
    "regime_threshold_urban": float,
}


def _apply_fields(config: ResearchConfig, data: dict):
    for field, expected_type in _CONFIG_WRITABLE_FIELDS.items():
        if field in data:
            value = data[field]
            # Allow null for date fields
            if field in ("date_from", "date_to") and value is None:
                setattr(config, field, None)
            elif value is not None:
                setattr(config, field, value)


# CONFIG ENDPOINTS

