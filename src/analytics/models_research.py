"""
Research Pipeline Configuration Models.

Central configuration for the Research Pipeline — allows UI-driven
control over geometry type, variable Y, spatial weight matrix,
model selection, OSM predictors, and diagnostics.

Models:
- ResearchConfig: pipeline configuration (singleton-active pattern)
- ResearchRun: execution history with config snapshot
- ResearchStepLog: per-step logs (R / Python / SQL)
- ResearchDiagnostics: Moran I, LM tests, model fit, LISA
"""

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


# =============================================================================
# CHOICES
# =============================================================================

class GeometryType(models.TextChoices):
    VORONOI = 'voronoi', 'Voronoi tessellation'
    GRID_500 = 'grid_500', 'Regular grid 500m'


class PopulationMethod(models.TextChoices):
    SPATIAL_JOIN = 'spatial_join', 'Area-weighted spatial join (GUS 500m)'
    POINTS = 'points', 'Point-in-polygon count'
    CENTROID = 'centroid', 'Centroid lookup'


class YFormula(models.TextChoices):
    COUNT_POP = 'count_pop', 'sighting_count / population'
    INV_POP = 'inv_pop', '1 / (population + 1)'
    LOG_POP = 'log_pop', 'log(population + 1)'
    LOG_COUNT = 'log_count', 'log(sighting_count + 1)'  # NEW: Direct measure of boar presence
    BINARY = 'binary', 'binary (0/1 sighting presence)'


class WMethod(models.TextChoices):
    KNN_AIC = 'knn_aic', 'KNN with AIC selection'
    CONTIGUITY = 'contiguity', 'Queen contiguity'
    TESSW = 'tessw', 'tessW (spatialWarsaw)'


class ModelTypeChoice(models.TextChoices):
    AUTO = 'auto', 'Auto (select by LM tests)'
    SAR = 'sar', 'SAR (Spatial Lag)'
    SEM = 'sem', 'SEM (Spatial Error)'
    SDM = 'sdm', 'SDM (Spatial Durbin)'
    PROBIT = 'probit', 'Spatial Probit'
    LOGIT = 'logit', 'Spatial Logit'


class RegimeType(models.TextChoices):
    NONE = 'none', 'Brak (jeden globalny model)'
    TRINARY = 'trinary', 'Trinary (las/miasto/mixed)'


class RunStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    RUNNING = 'running', 'Running'
    SUCCESS = 'success', 'Success'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class StepType(models.TextChoices):
    R = 'R', 'R script'
    PYTHON = 'Python', 'Python'
    SQL = 'SQL', 'SQL query'


class StepStatus(models.TextChoices):
    RUNNING = 'running', 'Running'
    SUCCESS = 'success', 'Success'
    FAILED = 'failed', 'Failed'
    SKIPPED = 'skipped', 'Skipped'


# All available OSM predictor names
ALL_PREDICTORS = [
    'forests', 'buildings', 'roads', 'water', 'parks',
    'meadow', 'farmland', 'allotments', 'scrub', 'railway', 'barriers',
]


# =============================================================================
# ResearchConfig
# =============================================================================

class ResearchConfig(models.Model):
    """
    Central configuration for Research Pipeline.

    Singleton-active pattern: only one config can have is_active=True.
    All parameters are exposed in the UI for interactive experimentation.
    """

    # -- Meta --
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name for this configuration profile",
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Only one configuration can be active at a time",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # -- Geometry --
    geometry_type = models.CharField(
        max_length=20,
        choices=GeometryType.choices,
        default=GeometryType.VORONOI,
        help_text="Spatial unit type for analysis",
    )

    # -- Population --
    population_method = models.CharField(
        max_length=20,
        choices=PopulationMethod.choices,
        default=PopulationMethod.SPATIAL_JOIN,
        help_text="How to assign population to spatial units",
    )

    # -- Variable Y --
    y_formula = models.CharField(
        max_length=20,
        choices=YFormula.choices,
        default=YFormula.LOG_POP,
        help_text="Dependent variable formula",
    )

    # -- Spatial weights matrix W --
    w_method = models.CharField(
        max_length=20,
        choices=WMethod.choices,
        default=WMethod.KNN_AIC,
        help_text="Spatial weight matrix construction method",
    )
    k_range_min = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(1)],
        help_text="Minimum k for KNN range search",
    )
    k_range_max = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(2)],
        help_text="Maximum k for KNN range search",
    )

    # -- Model --
    model_type = models.CharField(
        max_length=20,
        choices=ModelTypeChoice.choices,
        default=ModelTypeChoice.AUTO,
        help_text="Spatial model type (auto = selected by LM tests)",
    )

    # -- OSM predictors --
    active_predictors = models.JSONField(
        default=list,
        help_text="List of active OSM predictor names",
    )

    # -- Diagnostics --
    run_moran = models.BooleanField(
        default=True,
        help_text="Run Moran's I test for spatial autocorrelation",
    )
    run_lm_tests = models.BooleanField(
        default=True,
        help_text="Run LM lag/error tests for model selection",
    )
    run_lisa = models.BooleanField(
        default=False,
        help_text="Run Local Indicators of Spatial Association",
    )
    run_eta = models.BooleanField(
        default=False,
        help_text="Run ETA (Entropy-Tessellation-Agglomeration)",
    )

    # -- Thresholds --
    vif_threshold = models.FloatField(
        default=5.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(100.0)],
        help_text="VIF threshold for multicollinearity check",
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Research Configuration'
        verbose_name_plural = 'Research Configurations'

    def __str__(self):
        return f"{self.name} ({self.geometry_type}/{self.model_type})"
