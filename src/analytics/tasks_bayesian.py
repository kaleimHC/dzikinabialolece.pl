import logging

logger = logging.getLogger(__name__)


def check_n_minimum(n_obs: int, model_type: str) -> dict:
    """
    Check if sample size meets minimum requirements for ETA/GWR models.

    Args:
        n_obs: Number of observations
        model_type: One of 'eta', 'gwr', 'bayesian'

    Returns:
        Dict with 'ok', 'warning', 'error', 'message'
    """
    from .models_config import N_MINIMUM_REQUIREMENTS

    if model_type not in N_MINIMUM_REQUIREMENTS:
        return {"ok": True, "warning": None, "error": None, "message": None}

    req = N_MINIMUM_REQUIREMENTS[model_type]

    if "min" in req and n_obs < req["min"]:
        return {
            "ok": False,
            "warning": None,
            "error": True,
            "message": f"{req['message']}. N={n_obs} < {req['min']}",
        }

    if "warn" in req:
        if n_obs < req["warn"]:
            return {
                "ok": False,
                "warning": True,
                "error": True,
                "message": f"{req['message']}. N={n_obs} < {req['warn']}",
            }
        if n_obs < req.get("recommended", req["warn"]):
            return {
                "ok": True,
                "warning": True,
                "error": None,
                "message": f"N={n_obs} poniżej zalecanego {req['recommended']}. {req['message']}",
            }

    return {"ok": True, "warning": None, "error": None, "message": None}
