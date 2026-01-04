"""
Django Admin for Analytics app.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import AnalyticsRun, ModelPrediction


# ANALYTICS RUN ADMIN


@admin.register(AnalyticsRun)
class AnalyticsRunAdmin(admin.ModelAdmin):
    """Admin for viewing pipeline execution history."""

    list_display = [
        "task_id",
        "task_name",
        "status_display",
        "started_at",
        "duration_display",
    ]

    list_filter = [
        "status",
        "task_name",
    ]

    search_fields = [
        "task_id",
        "task_name",
    ]

    readonly_fields = [
        "task_id",
        "task_name",
        "status",
        "started_at",
        "completed_at",
        "duration_seconds",
        "result_summary",
        "error_message",
        "parameters",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def status_display(self, obj):
        colors = {
            "pending": "gray",
            "running": "blue",
            "completed": "green",
            "failed": "red",
        }
        color = colors.get(obj.status, "black")
        return format_html('<span style="color: {};">{}</span>', color, obj.status)

    status_display.short_description = "Status"

    def duration_display(self, obj):
        if obj.duration_seconds is None:
            return "-"
        if obj.duration_seconds < 60:
            return f"{obj.duration_seconds:.1f}s"
        if obj.duration_seconds < 3600:
            return f"{obj.duration_seconds / 60:.1f}m"
        return f"{obj.duration_seconds / 3600:.1f}h"

    duration_display.short_description = "Duration"


# MODEL PREDICTION ADMIN (existing model)


@admin.register(ModelPrediction)
class ModelPredictionAdmin(admin.ModelAdmin):
    """Admin for model predictions."""

    list_display = [
        "grid_cell",
        "model_type",
        "prediction_value",
        "prediction_date",
    ]

    list_filter = [
        "model_type",
        "prediction_date",
    ]


# PARAMETER CONFIGURATION ADMIN

from .models_config import ParameterConfiguration


@admin.register(ParameterConfiguration)
class ParameterConfigurationAdmin(admin.ModelAdmin):
    """Admin for named parameter configurations. Only ONE config can be active."""

    list_display = [
        "name",
        "is_active",
        "updated_at",
    ]

    list_filter = [
        "is_active",
    ]

    search_fields = ["name", "description"]

    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Identification", {"fields": ("name", "description", "is_active")}),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["activate_config", "deactivate_config"]

    @admin.action(description="Activate selected configuration")
    def activate_config(self, request, queryset):
        if queryset.count() > 1:
            self.message_user(
                request, "Only one configuration can be active!", level="error"
            )
            return
        # Deactivate all others
        ParameterConfiguration.objects.update(is_active=False)
        queryset.update(is_active=True)
        self.message_user(request, "Configuration activated.")

    @admin.action(description="Deactivate selected configuration")
    def deactivate_config(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Configuration(s) deactivated.")


# RESEARCH PIPELINE MODELS

from .models_research import (
    ResearchConfig,
    ResearchRun,
    ResearchStepLog,
    ResearchDiagnostics,
)


@admin.register(ResearchConfig)
class ResearchConfigAdmin(admin.ModelAdmin):
    """Admin for Research Pipeline configuration."""

    list_display = [
        "name",
        "is_active",
        "geometry_type",
        "y_formula",
        "model_type",
        "w_method",
        "predictor_count",
        "updated_at",
    ]

    list_filter = [
        "is_active",
        "geometry_type",
        "y_formula",
        "model_type",
        "w_method",
    ]

    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Identification",
            {
                "fields": ("name", "is_active"),
            },
        ),
        (
            "Geometry & Population",
            {
                "fields": ("geometry_type", "population_method"),
            },
        ),
        (
            "Variable Y",
            {
                "fields": ("y_formula",),
                "description": "Voronoi + count_pop is blocked (count=1 always)",
            },
        ),
        (
            "Spatial Weights Matrix W",
            {
                "fields": ("w_method", "k_range_min", "k_range_max"),
            },
        ),
        (
            "Model",
            {
                "fields": ("model_type",),
            },
        ),
        (
            "OSM Predictors",
            {
                "fields": ("active_predictors",),
                "description": 'JSON list: ["forests","buildings","roads","water","parks","meadow","farmland","allotments","scrub","railway","barriers"]',
            },
        ),
        (
            "Diagnostics",
            {
                "fields": ("run_moran", "run_lm_tests", "run_lisa", "run_eta"),
            },
        ),
        (
            "Thresholds",
            {
                "fields": ("vif_threshold", "alpha", "seed"),
                "classes": ("collapse",),
            },
        ),
        (
            "Temporal Filter",
            {
                "fields": ("date_from", "date_to"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["activate_research_config", "deactivate_research_config"]

    def predictor_count(self, obj):
        preds = obj.active_predictors or []
        return len(preds)

    predictor_count.short_description = "Predictors"

    @admin.action(description="Activate selected research config")
    def activate_research_config(self, request, queryset):
        if queryset.count() > 1:
            self.message_user(request, "Only one config can be active!", level="error")
            return
        ResearchConfig.objects.update(is_active=False)
        queryset.update(is_active=True)
        self.message_user(request, "Research config activated.")

    @admin.action(description="Deactivate selected research config")
    def deactivate_research_config(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Research config(s) deactivated.")


@admin.register(ResearchRun)
class ResearchRunAdmin(admin.ModelAdmin):
    """Admin for Research Pipeline execution history."""

    list_display = [
        "short_id",
        "config",
        "status_display",
        "n_sightings",
        "n_cells",
        "started_at",
        "duration_display",
    ]

    list_filter = ["status"]
    search_fields = ["id", "config__name"]

    readonly_fields = [
        "id",
        "config",
        "config_snapshot",
        "started_at",
        "finished_at",
        "status",
        "n_sightings",
        "n_cells",
        "error_message",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def short_id(self, obj):
        return str(obj.id)[:8]

    short_id.short_description = "Run ID"

    def status_display(self, obj):
        colors = {
            "pending": "gray",
            "running": "blue",
            "success": "green",
            "failed": "red",
            "cancelled": "orange",
        }
        color = colors.get(obj.status, "black")
        return format_html('<span style="color: {};">{}</span>', color, obj.status)

    status_display.short_description = "Status"

    def duration_display(self, obj):
        if not obj.finished_at or not obj.started_at:
            return "-"
        delta = (obj.finished_at - obj.started_at).total_seconds()
        if delta < 60:
            return f"{delta:.1f}s"
        return f"{delta / 60:.1f}m"

    duration_display.short_description = "Duration"


@admin.register(ResearchStepLog)
class ResearchStepLogAdmin(admin.ModelAdmin):
    """Admin for per-step execution logs."""

    list_display = [
        "run_short",
        "step_order",
        "step_name",
        "step_type",
        "status_display",
        "exit_code",
        "duration_seconds",
    ]

    list_filter = ["status", "step_type"]

    readonly_fields = [
        "run",
        "step_name",
        "step_order",
        "step_type",
        "started_at",
        "finished_at",
        "duration_seconds",
        "exit_code",
        "status",
        "input_params",
        "output_stats",
        "stdout",
        "stderr",
        "errors",
        "warnings",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def run_short(self, obj):
        return str(obj.run_id)[:8]

    run_short.short_description = "Run"

    def status_display(self, obj):
        colors = {
            "running": "blue",
            "success": "green",
            "failed": "red",
            "skipped": "gray",
        }
        color = colors.get(obj.status, "black")
        return format_html('<span style="color: {};">{}</span>', color, obj.status)

    status_display.short_description = "Status"


@admin.register(ResearchDiagnostics)
class ResearchDiagnosticsAdmin(admin.ModelAdmin):
    """Admin for diagnostic test results."""

    list_display = [
        "run",
        "model_selected",
        "aic",
        "moran_summary",
        "lisa_summary",
    ]

    readonly_fields = [
        "run",
        "moran_i",
        "moran_expected",
        "moran_variance",
        "moran_z",
        "moran_p",
        "lm_lag_stat",
        "lm_lag_p",
        "lm_error_stat",
        "lm_error_p",
        "rlm_lag_stat",
        "rlm_lag_p",
        "rlm_error_stat",
        "rlm_error_p",
        "model_selected",
        "aic",
        "log_likelihood",
        "coefficients",
        "r_squared",
        "rho",
        "lambda_param",
        "lisa_hh_count",
        "lisa_ll_count",
        "lisa_hl_count",
        "lisa_lh_count",
        "lisa_ns_count",
        "vif_results",
        "predictors_dropped",
    ]

    fieldsets = (
        (
            "Run",
            {
                "fields": ("run",),
            },
        ),
        (
            "Moran's I",
            {
                "fields": (
                    "moran_i",
                    "moran_expected",
                    "moran_variance",
                    "moran_z",
                    "moran_p",
                ),
            },
        ),
        (
            "LM Tests",
            {
                "fields": (
                    "lm_lag_stat",
                    "lm_lag_p",
                    "lm_error_stat",
                    "lm_error_p",
                    "rlm_lag_stat",
                    "rlm_lag_p",
                    "rlm_error_stat",
                    "rlm_error_p",
                ),
                "description": "Lagrange Multiplier tests (post-hoc diagnostics; model selection uses AIC)",
            },
        ),
        (
            "Model Fit",
            {
                "fields": (
                    "model_selected",
                    "aic",
                    "log_likelihood",
                    "r_squared",
                    "coefficients",
                ),
            },
        ),
        (
            "Spatial Parameters",
            {
                "fields": ("rho", "lambda_param"),
            },
        ),
        (
            "LISA",
            {
                "fields": (
                    "lisa_hh_count",
                    "lisa_ll_count",
                    "lisa_hl_count",
                    "lisa_lh_count",
                    "lisa_ns_count",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "VIF",
            {
                "fields": ("vif_results", "predictors_dropped"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def moran_summary(self, obj):
        if obj.moran_i is None:
            return "-"
        sig = (
            "***"
            if obj.moran_p and obj.moran_p < 0.001
            else (
                "**"
                if obj.moran_p and obj.moran_p < 0.01
                else ("*" if obj.moran_p and obj.moran_p < 0.05 else "ns")
            )
        )
        return f"I={obj.moran_i:.4f} {sig}"

    moran_summary.short_description = "Moran's I"

    def lisa_summary(self, obj):
        if obj.lisa_hh_count is None:
            return "-"
        return f"HH={obj.lisa_hh_count} LL={obj.lisa_ll_count}"

    lisa_summary.short_description = "LISA"
