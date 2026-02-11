"""
URL routing for Analytics app.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Grid endpoints (IZOLACJA: trzy osobne źródła danych)
    path("grid/", views.grid_cells, name="grid-cells"),  # FAST mode - siatka kwadratowa
    path("voronoi/", views.voronoi_cells, name="voronoi-cells"),  # PUB mode - Voronoi
    path(
        "research-grid/", views.research_grid_cells, name="research-grid-cells"
    ),  # RESEARCH mode (voronoi)
    path(
        "research-grid-500/", views.research_grid_500, name="research-grid-500"
    ),  # RESEARCH mode (500m)
    path(
        "voronoi/features/", views.calculate_voronoi_features, name="voronoi-features"
    ),
    path("risk/", views.risk_heatmap, name="risk-heatmap"),
    path("predictions/", views.predictions_list, name="predictions"),
    path("status/", views.task_status, name="task_status"),
    path("boundaries/", views.boundaries, name="boundaries"),
    path("buildings/", views.buildings, name="buildings"),
    path("forests/", views.forests, name="forests"),
    path("water/", views.water, name="water"),
    path("waterways/", views.waterways, name="waterways"),
    path("barriers/", views.barriers, name="barriers"),
    path("roads/", views.roads, name="roads"),
    path("allotments/", views.allotments, name="allotments"),
    path("meadows/", views.meadows, name="meadows"),
    path("farmland/", views.farmland, name="farmland"),
    path("parks/", views.parks, name="parks"),
    path("scrub/", views.scrub, name="scrub"),
    path("railway/", views.railway, name="railway"),
    path("population/", views.population, name="population"),
    # Dev-only: R pipeline recalculation
    path("recalculate/", views.recalculate, name="recalculate"),
    path("recalculate/status/", views.recalculate_status, name="recalculate-status"),
    # Sample switching (test datasets)
    path("samples/current/", views.samples_current, name="samples-current"),
    path("samples/switch/", views.samples_switch, name="samples-switch"),
    path(
        "tasks/<str:task_id>/status/",
        views.sample_task_progress,
        name="sample-task-progress",
    ),
    # Bayesian Layer (MASTER_SPEC v2.3)
    path("bayesian/", views.bayesian_results, name="bayesian-results"),
    path("bayesian/run/", views.bayesian_run, name="bayesian-run"),
    path(
        "bayesian/diagnostics/", views.bayesian_diagnostics, name="bayesian-diagnostics"
    ),
    path("priors/", views.prior_configs, name="prior-configs"),
    # Configuration & Presets
    path("presets/", views.presets_list, name="presets-list"),
    path("config/apply-preset/", views.apply_preset, name="apply-preset"),
    path("config/active/", views.active_config, name="active-config"),
    # spatialWarsaw results (ETA, Spatial Models)
    path("eta/current/", views.eta_current, name="eta-current"),
    path("spatial/current/", views.spatial_current, name="spatial-current"),
    # W matrix visualization
    path("w-matrix/edges/", views.w_matrix_edges, name="w-matrix-edges"),
    # Combined Results & Export (FAZA 5)
    path("results/combined/", views.combined_results, name="combined-results"),
    path("results/export/", views.export_results_csv, name="export-results"),
    # Mode Router (FAST/PUB/BAYES pipeline separation)
    path("pipeline/", views.run_mode_pipeline, name="run-pipeline"),
    path("pipeline/modes/", views.pipeline_modes, name="pipeline-modes"),
    path(
        "pipeline/<str:task_id>/status/", views.pipeline_status, name="pipeline-status"
    ),
]
