"""
Django Admin for Analytics app.
MASTER_SPEC v2.3 - Bayesian Integration Layer

Admin interfaces for:
- PriorConfig: Prior configuration management
- BayesianResult: MCMC results (read-only)
- AnalyticsRun: Pipeline execution history
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import AnalyticsRun, ModelPrediction
from .models_bayesian import PriorConfig, BayesianResult


# =============================================================================
# PRIOR CONFIG ADMIN
# =============================================================================

@admin.register(PriorConfig)
class PriorConfigAdmin(admin.ModelAdmin):
    """
    Admin for managing Bayesian prior configurations.

    ADR-011: Prior Elicitation Strategy
    - Audit trail showing source values (H_rel, ARI, bandwidth)
    - Active/inactive management for versioning
    """

    list_display = [
        'parameter_name',
        'dist_type',
        'alpha_hyper',
        'beta_hyper',
        'model_version',
        'is_active',
        'created_at',
        'source_display',
    ]

    list_filter = [
        'is_active',
        'parameter_name',
        'dist_type',
        'model_version',
    ]

    search_fields = [
        'model_version',
        'parameter_name',
    ]

    readonly_fields = [
        'id',
        'created_at',
        'created_by',
    ]

    fieldsets = (
        ('Identification', {
            'fields': ('id', 'model_version', 'is_active')
        }),
        ('Prior Distribution', {
            'fields': ('parameter_name', 'dist_type', 'alpha_hyper', 'beta_hyper'),
            'description': 'ADR-011: delta ~ Beta(kappa*H_rel, kappa*(1-H_rel)), rho ~ Beta(kappa*ARI, kappa*(1-ARI))'
        }),
        ('Audit Trail (Source Values)', {
            'fields': ('source_h_rel', 'source_ari', 'source_bandwidth'),
            'classes': ('collapse',),
            'description': 'Values from frequentist analysis used to derive these priors'
        }),
        ('Metadata', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',),
        }),
    )

    actions = ['activate_priors', 'deactivate_priors']

    def source_display(self, obj):
        """Display source values in a compact format."""
        parts = []
        if obj.source_h_rel:
            parts.append(f"H_rel={obj.source_h_rel}")
        if obj.source_ari:
            parts.append(f"ARI={obj.source_ari}")
        if obj.source_bandwidth:
            parts.append(f"bw={obj.source_bandwidth}m")
        return ", ".join(parts) if parts else "-"
    source_display.short_description = "Source Values"

    @admin.action(description="Activate selected prior configs")
    def activate_priors(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activated {updated} prior configs.")

    @admin.action(description="Deactivate selected prior configs")
    def deactivate_priors(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} prior configs.")


# =============================================================================
# BAYESIAN RESULT ADMIN (Read-only)
# =============================================================================

@admin.register(BayesianResult)
class BayesianResultAdmin(admin.ModelAdmin):
    """
    Admin for viewing Bayesian SSM results.

    Read-only - results are written by R scripts (06_bayesian_ssm.R).
    """

    list_display = [
        'cell_id',
        'grid_type',
        'intensity_mean',
        'ci_display',
        'convergence_status',
        'prob_above_threshold',
        'computed_at',
    ]

    list_filter = [
        'grid_type',
        'execution__task_name',
        ('r_hat', admin.EmptyFieldListFilter),
    ]

    search_fields = [
        'cell_id',
        'execution__task_id',
    ]

    readonly_fields = [
        'id',
        'execution',
        'cell_id',
        'grid_type',
        'intensity_mean',
        'intensity_median',
        'ci_lower_95',
        'ci_upper_95',
        'ci_lower_50',
        'ci_upper_50',
        'prob_above_threshold',
        'r_hat',
        'ess_bulk',
        'ess_tail',
        'waic',
        'loo_ic',
        'computed_at',
    ]

    fieldsets = (
        ('Cell Info', {
            'fields': ('id', 'execution', 'cell_id', 'grid_type')
        }),
        ('Posterior Summary', {
            'fields': ('intensity_mean', 'intensity_median', 'prob_above_threshold'),
        }),
        ('Credible Intervals', {
            'fields': ('ci_lower_95', 'ci_upper_95', 'ci_lower_50', 'ci_upper_50'),
        }),
        ('MCMC Diagnostics', {
            'fields': ('r_hat', 'ess_bulk', 'ess_tail'),
            'description': 'R-hat < 1.01 and ESS > 400 required for publication quality'
        }),
        ('Model Comparison', {
            'fields': ('waic', 'loo_ic'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('computed_at',),
        }),
    )

    def has_add_permission(self, request):
        return False  # Read-only

    def has_change_permission(self, request, obj=None):
        return False  # Read-only

    def ci_display(self, obj):
        """Display 95% CI in compact format."""
        return f"[{obj.ci_lower_95:.3f}, {obj.ci_upper_95:.3f}]"
    ci_display.short_description = "95% CI"

    def convergence_status(self, obj):
        """Display convergence status with color coding."""
        if obj.r_hat is None:
            return format_html('<span style="color: gray;">N/A</span>')

        if obj.r_hat < 1.01 and (obj.ess_bulk is None or obj.ess_bulk > 400):
            return format_html('<span style="color: green;">R-hat={:.3f}</span>', obj.r_hat)
        elif obj.r_hat < 1.05:
            return format_html('<span style="color: orange;">R-hat={:.3f}</span>', obj.r_hat)
        else:
            return format_html('<span style="color: red;">R-hat={:.3f}</span>', obj.r_hat)
    convergence_status.short_description = "Convergence"


# =============================================================================
# ANALYTICS RUN ADMIN
# =============================================================================

@admin.register(AnalyticsRun)
class AnalyticsRunAdmin(admin.ModelAdmin):
    """Admin for viewing pipeline execution history."""

    list_display = [
        'task_id',
        'task_name',
        'status_display',
        'started_at',
        'duration_display',
    ]

    list_filter = [
        'status',
        'task_name',
    ]

    search_fields = [
        'task_id',
        'task_name',
    ]

    readonly_fields = [
        'task_id',
        'task_name',
        'status',
        'started_at',
        'completed_at',
        'duration_seconds',
        'result_summary',
        'error_message',
        'parameters',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'pending': 'gray',
            'running': 'blue',
            'completed': 'green',
            'failed': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.status)
    status_display.short_description = "Status"

    def duration_display(self, obj):
        """Display duration in human-readable format."""
        if obj.duration_seconds is None:
            return "-"
        if obj.duration_seconds < 60:
            return f"{obj.duration_seconds:.1f}s"
        if obj.duration_seconds < 3600:
            return f"{obj.duration_seconds / 60:.1f}m"
        return f"{obj.duration_seconds / 3600:.1f}h"
    duration_display.short_description = "Duration"


# =============================================================================
# MODEL PREDICTION ADMIN (existing model)
# =============================================================================

@admin.register(ModelPrediction)
class ModelPredictionAdmin(admin.ModelAdmin):
    """Admin for model predictions."""

    list_display = [
        'grid_cell',
        'model_type',
        'prediction_value',
        'prediction_date',
    ]

    list_filter = [
        'model_type',
        'prediction_date',
    ]


# =============================================================================
# PARAMETER CONFIGURATION ADMIN (MASTER_SPEC v2.3 Section I.5)
# =============================================================================

from .models_config import ParameterConfiguration

@admin.register(ParameterConfiguration)
class ParameterConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for managing Bayesian layer parameters.
    
    Only ONE configuration can be active at a time.
    Validates: rho + delta < 1.0 (stationarity)
    """
    
    list_display = [
        'name',
        'is_active',
        'bayesian_kappa',
        'persistence_rho_mean',
        'diffusion_delta_mean',
        'stationarity_check',
        'weights_display',
        'updated_at',
    ]
    
    list_filter = [
        'is_active',
        'bayesian_enabled',
    ]
    
    search_fields = ['name', 'description']
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Identification', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Bayesian Priors (ADR-011)', {
            'fields': (
                'bayesian_kappa',
                'persistence_rho_mean',
                'diffusion_delta_mean',
            ),
            'description': 'rho + delta MUST be < 1.0 for model stationarity'
        }),
        ('MCMC Settings', {
            'fields': (
                'mcmc_iterations',
                'mcmc_warmup',
                'mcmc_chains',
                'mcmc_adapt_delta',
                'mcmc_seed',
            ),
            'classes': ('collapse',),
        }),
        ('Feature Flags (ADR-014)', {
            'fields': ('bayesian_enabled',),
        }),
        ('Ensemble Weights (must sum to 1.0)', {
            'fields': (
                'weight_rf',
                'weight_gwr',
                'weight_eta',
            ),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    actions = ['activate_config', 'deactivate_config']
    
    def stationarity_check(self, obj):
        """Display rho + delta with color coding."""
        rho = float(obj.persistence_rho_mean or 0)
        delta = float(obj.diffusion_delta_mean or 0)
        total = rho + delta

        if total < 0.9:
            color = 'green'
        elif total < 1.0:
            color = 'orange'
        else:
            color = 'red'

        return format_html(
            '<span style="color: {};">ρ+δ = {}</span>',
            color, f"{total:.3f}"
        )
    stationarity_check.short_description = "Stationarity"
    
    def weights_display(self, obj):
        """Display weights sum."""
        total = float(obj.weight_rf + obj.weight_gwr + obj.weight_eta)
        color = 'green' if 0.99 <= total <= 1.01 else 'red'
        return format_html('<span style="color: {};">Σ = {}</span>', color, f"{total:.3f}")
    weights_display.short_description = "Weights"
    
    @admin.action(description="Activate selected configuration")
    def activate_config(self, request, queryset):
        if queryset.count() > 1:
            self.message_user(request, "Only one configuration can be active!", level='error')
            return
        # Deactivate all others
        ParameterConfiguration.objects.update(is_active=False)
        queryset.update(is_active=True)
        self.message_user(request, "Configuration activated.")
    
    @admin.action(description="Deactivate selected configuration")
    def deactivate_config(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Configuration(s) deactivated.")


# =============================================================================
# RESEARCH PIPELINE MODELS
# =============================================================================

from .models_research import (
    ResearchConfig, ResearchRun, ResearchStepLog, ResearchDiagnostics,
)


@admin.register(ResearchConfig)
class ResearchConfigAdmin(admin.ModelAdmin):
    """Admin for Research Pipeline configuration."""

    list_display = [
        'name',
        'is_active',
        'geometry_type',
        'y_formula',
        'model_type',
        'w_method',
        'predictor_count',
        'updated_at',
    ]

    list_filter = [
        'is_active',
        'geometry_type',
        'y_formula',
        'model_type',
        'w_method',
    ]

    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Identification', {
            'fields': ('name', 'is_active'),
        }),
        ('Geometry & Population', {
            'fields': ('geometry_type', 'population_method'),
        }),
        ('Variable Y', {
            'fields': ('y_formula',),
            'description': 'Voronoi + count_pop is blocked (count=1 always)',
        }),
        ('Spatial Weights Matrix W', {
            'fields': ('w_method', 'k_range_min', 'k_range_max'),
        }),
        ('Model', {
            'fields': ('model_type',),
        }),
        ('OSM Predictors', {
            'fields': ('active_predictors',),
            'description': 'JSON list: ["forests","buildings","roads","water","parks","meadow","farmland","allotments","scrub","railway","barriers"]',
        }),
        ('Diagnostics', {
            'fields': ('run_moran', 'run_lm_tests', 'run_lisa', 'run_eta'),
        }),
        ('Thresholds', {
            'fields': ('vif_threshold', 'alpha', 'seed'),
            'classes': ('collapse',),
        }),
        ('Temporal Filter', {
            'fields': ('date_from', 'date_to'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['activate_research_config', 'deactivate_research_config']

    def predictor_count(self, obj):
        preds = obj.active_predictors or []
        return len(preds)
    predictor_count.short_description = "Predictors"

    @admin.action(description="Activate selected research config")
    def activate_research_config(self, request, queryset):
        if queryset.count() > 1:
            self.message_user(request, "Only one config can be active!", level='error')
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
        'short_id',
        'config',
        'status_display',
        'n_sightings',
        'n_cells',
        'started_at',
        'duration_display',
    ]

    list_filter = ['status']
    search_fields = ['id', 'config__name']

    readonly_fields = [
        'id', 'config', 'config_snapshot', 'started_at', 'finished_at',
        'status', 'n_sightings', 'n_cells', 'error_message',
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
            'pending': 'gray', 'running': 'blue',
            'success': 'green', 'failed': 'red', 'cancelled': 'orange',
        }
        color = colors.get(obj.status, 'black')
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
        'run_short',
        'step_order',
        'step_name',
        'step_type',
        'status_display',
        'exit_code',
        'duration_seconds',
    ]

    list_filter = ['status', 'step_type']

    readonly_fields = [
        'run', 'step_name', 'step_order', 'step_type',
        'started_at', 'finished_at', 'duration_seconds',
        'exit_code', 'status', 'input_params', 'output_stats',
        'stdout', 'stderr', 'errors', 'warnings',
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
            'running': 'blue', 'success': 'green',
            'failed': 'red', 'skipped': 'gray',
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.status)
    status_display.short_description = "Status"


@admin.register(ResearchDiagnostics)
class ResearchDiagnosticsAdmin(admin.ModelAdmin):
    """Admin for diagnostic test results."""

    list_display = [
        'run',
        'model_selected',
        'aic',
        'moran_summary',
        'lisa_summary',
    ]

    readonly_fields = [
        'run',
        'moran_i', 'moran_expected', 'moran_variance', 'moran_z', 'moran_p',
        'lm_lag_stat', 'lm_lag_p', 'lm_error_stat', 'lm_error_p',
        'rlm_lag_stat', 'rlm_lag_p', 'rlm_error_stat', 'rlm_error_p',
        'model_selected', 'aic', 'log_likelihood', 'coefficients', 'r_squared',
        'rho', 'lambda_param',
        'lisa_hh_count', 'lisa_ll_count', 'lisa_hl_count', 'lisa_lh_count', 'lisa_ns_count',
        'vif_results', 'predictors_dropped',
    ]

    fieldsets = (
        ('Run', {
            'fields': ('run',),
        }),
        ("Moran's I", {
            'fields': ('moran_i', 'moran_expected', 'moran_variance', 'moran_z', 'moran_p'),
        }),
        ('LM Tests', {
            'fields': (
                'lm_lag_stat', 'lm_lag_p',
                'lm_error_stat', 'lm_error_p',
                'rlm_lag_stat', 'rlm_lag_p',
                'rlm_error_stat', 'rlm_error_p',
            ),
            'description': 'Lagrange Multiplier tests for SAR vs SEM selection',
        }),
        ('Model Fit', {
            'fields': ('model_selected', 'aic', 'log_likelihood', 'r_squared', 'coefficients'),
        }),
        ('Spatial Parameters', {
            'fields': ('rho', 'lambda_param'),
        }),
        ('LISA', {
            'fields': ('lisa_hh_count', 'lisa_ll_count', 'lisa_hl_count', 'lisa_lh_count', 'lisa_ns_count'),
            'classes': ('collapse',),
        }),
        ('VIF', {
            'fields': ('vif_results', 'predictors_dropped'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def moran_summary(self, obj):
        if obj.moran_i is None:
            return "-"
        sig = "***" if obj.moran_p and obj.moran_p < 0.001 else (
            "**" if obj.moran_p and obj.moran_p < 0.01 else (
                "*" if obj.moran_p and obj.moran_p < 0.05 else "ns"
            )
        )
        return f"I={obj.moran_i:.4f} {sig}"
    moran_summary.short_description = "Moran's I"

    def lisa_summary(self, obj):
        if obj.lisa_hh_count is None:
            return "-"
        return f"HH={obj.lisa_hh_count} LL={obj.lisa_ll_count}"
    lisa_summary.short_description = "LISA"
