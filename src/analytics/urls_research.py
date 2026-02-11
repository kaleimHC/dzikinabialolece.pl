"""
URL routing for Research Pipeline API.

All endpoints under /api/research/ prefix (registered in dziki/urls.py).
"""

from django.urls import path
from . import views_research as views

urlpatterns = [
    # Configuration
    path("configs/", views.config_list, name="research-config-list"),
    path(
        "configs/<int:config_id>/", views.config_detail, name="research-config-detail"
    ),
    path(
        "configs/<int:config_id>/activate/",
        views.config_activate,
        name="research-config-activate",
    ),
    # Pipeline execution
    path("run/", views.run_pipeline, name="research-run"),
    # Run history & results
    path("runs/", views.run_list, name="research-run-list"),
    path("runs/clear/", views.run_clear_all, name="research-run-clear"),
    path("runs/<uuid:run_id>/", views.run_detail, name="research-run-detail"),
    path("runs/<uuid:run_id>/steps/", views.run_steps, name="research-run-steps"),
    path(
        "runs/<uuid:run_id>/diagnostics/",
        views.run_diagnostics,
        name="research-run-diagnostics",
    ),
    # Status overview
    path("status/", views.pipeline_status, name="research-status"),
    # Distributions (for regime threshold UI)
    path("distributions/", views.distributions, name="research-distributions"),
    # Generate preview (async geometry + OSM features for regime threshold preview)
    path("generate-preview/", views.generate_preview, name="research-generate-preview"),
    path(
        "preview-status/<str:task_id>/",
        views.preview_status,
        name="research-preview-status",
    ),
    # Spatial impacts (SAR/SDM only) - LeSage & Pace (2009)
    path("impacts/", views.spatial_impacts, name="research-impacts"),
]
