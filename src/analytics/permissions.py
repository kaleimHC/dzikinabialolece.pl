from rest_framework.permissions import BasePermission
from rest_framework.throttling import AnonRateThrottle


class IsBearerAuthenticated(BasePermission):
    """
    Allows access only to authenticated users.
    Works with TokenAuthentication (Bearer token) and SessionAuthentication.
    Applied to write/compute endpoints — GET endpoints stay AllowAny globally.
    """

    message = (
        "Authentication required. Provide a valid Bearer token in Authorization header."
    )

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class PipelineRunThrottle(AnonRateThrottle):
    """Anti-bot safety valve on compute-triggering POST endpoints (pipeline run, preview)."""

    scope = "pipeline_run"


class SamplesSwitchThrottle(AnonRateThrottle):
    """Anti-bot safety valve on samples/switch (destructive POST)."""

    scope = "samples_switch"
