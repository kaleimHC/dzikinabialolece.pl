"""
Research Pipeline Configuration Models.

Central configuration for the Research Pipeline - allows UI-driven
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



class GeometryType(models.TextChoices):
    VORONOI = "voronoi", "Voronoi tessellation"
    GRID_500 = "grid_500", "Regular grid 500m"


class PopulationMethod(models.TextChoices):
    SPATIAL_JOIN = "spatial_join", "Area-weighted spatial join (GUS 500m)"
    POINTS = "points", "Point-in-polygon count"
    CENTROID = "centroid", "Centroid lookup"


class YFormula(models.TextChoices):
    LOG_INTENSITY = (
        "log_intensity",
        "log((sighting_count + 1) / area_km2) - risk signal (default)",
    )
    COUNT_POP = "count_pop", "sighting_count / population"
    INV_POP = "inv_pop", "1 / (population + 1)"
    LOG_POP = "log_pop", "log(population + 1)"
    LOG_COUNT = (
        "log_count",
        "log(sighting_count + 1)",
    )
    BINARY = "binary", "binary (0/1 sighting presence)"


class WMethod(models.TextChoices):
    KNN_AIC = "knn_aic", "KNN with AIC selection"
    CONTIGUITY = "contiguity", "Queen contiguity"
    TESSW = "tessw", "tessW (spatialWarsaw)"


class ModelTypeChoice(models.TextChoices):
    AUTO = "auto", "Auto (SAR vs SEM by AIC)"
    SAR = "sar", "SAR (Spatial Lag)"
    SEM = "sem", "SEM (Spatial Error)"
    SDM = "sdm", "SDM (Spatial Durbin)"
    PROBIT = "probit", "Spatial Probit"
    LOGIT = "logit", "Spatial Logit"


class RegimeType(models.TextChoices):
    NONE = "none", "Brak (jeden globalny model)"
    TRINARY = "trinary", "Trinary (las/miasto/mixed)"


class RunStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class StepType(models.TextChoices):
    R = "R", "R script"
    PYTHON = "Python", "Python"
    SQL = "SQL", "SQL query"


class StepStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


ALL_PREDICTORS = [
    "forests",
    "buildings",
    "roads",
    "water",
    "parks",
    "meadow",
    "farmland",
    "allotments",
    "scrub",
    "railway",
    "barriers",
]



class ResearchConfig(models.Model):
    """
    Central configuration for Research Pipeline.

    Singleton-active pattern: only one config can have is_active=True.
    All parameters are exposed in the UI for interactive experimentation.
    """

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

    geometry_type = models.CharField(
        max_length=20,
        choices=GeometryType.choices,
        default=GeometryType.VORONOI,
        help_text="Spatial unit type for analysis",
    )

    population_method = models.CharField(
        max_length=20,
        choices=PopulationMethod.choices,
        default=PopulationMethod.SPATIAL_JOIN,
        help_text="How to assign population to spatial units",
    )

    y_formula = models.CharField(
        max_length=20,
        choices=YFormula.choices,
        default=YFormula.LOG_INTENSITY,
        help_text="Dependent variable formula",
    )

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

    model_type = models.CharField(
        max_length=20,
        choices=ModelTypeChoice.choices,
        default=ModelTypeChoice.AUTO,
        help_text="Spatial model type (auto = SAR vs SEM by AIC; LM tests post-hoc only)",
    )

    active_predictors = models.JSONField(
        default=list,
        help_text="List of active OSM predictor names",
    )

    run_moran = models.BooleanField(
        default=True,
        help_text="Run Moran's I test for spatial autocorrelation",
    )
    run_lm_tests = models.BooleanField(
        default=True,
        help_text="Run LM lag/error tests as post-hoc diagnostics (not used for model selection)",
    )
    run_lisa = models.BooleanField(
        default=False,
        help_text="Run Local Indicators of Spatial Association",
    )
    run_eta = models.BooleanField(
        default=False,
        help_text="Run ETA (Entropy-Tessellation-Agglomeration)",
    )

    vif_threshold = models.FloatField(
        default=5.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(100.0)],
        help_text="VIF threshold for multicollinearity check",
    )
    alpha = models.FloatField(
        default=0.05,
        validators=[MinValueValidator(0.001), MaxValueValidator(0.5)],
        help_text="Significance level for statistical tests",
    )
    seed = models.PositiveIntegerField(
        default=42,
        help_text="Random seed for reproducibility",
    )

    date_from = models.DateField(
        null=True,
        blank=True,
        help_text="Include sightings from this date (inclusive)",
    )
    date_to = models.DateField(
        null=True,
        blank=True,
        help_text="Include sightings up to this date (inclusive)",
    )

    use_regime_model = models.BooleanField(
        default=False,
        help_text="Use regime model (trinary forest/urban/mixed)",
    )
    regime_type = models.CharField(
        max_length=20,
        choices=RegimeType.choices,
        default=RegimeType.NONE,
        help_text="Type of regime classification",
    )
    regime_threshold = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Forest cover threshold for regime classification (0-1)",
    )
    regime_threshold_urban = models.FloatField(
        default=0.15,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Building density threshold for urban regime (0-1)",
    )

    class Meta:
        verbose_name = "Research Config"
        verbose_name_plural = "Research Configs"
        ordering = ["-updated_at"]
        # DB-level defense-in-depth (mirrors migration 0007): the DB itself
        # rejects any config value/range a button could never emit.
        constraints = [
            models.CheckConstraint(check=models.Q(geometry_type__in=["voronoi", "grid_500"]), name="rc_geometry_type_valid"),
            models.CheckConstraint(check=models.Q(population_method__in=["spatial_join", "points", "centroid"]), name="rc_population_method_valid"),
            models.CheckConstraint(check=models.Q(y_formula__in=["log_intensity", "count_pop", "inv_pop", "log_pop", "log_count", "binary"]), name="rc_y_formula_valid"),
            models.CheckConstraint(check=models.Q(w_method__in=["knn_aic", "contiguity", "tessw"]), name="rc_w_method_valid"),
            models.CheckConstraint(check=models.Q(model_type__in=["auto", "sar", "sem", "sdm", "probit", "logit"]), name="rc_model_type_valid"),
            models.CheckConstraint(check=models.Q(regime_type__in=["none", "trinary"]), name="rc_regime_type_valid"),
            models.CheckConstraint(check=models.Q(k_range_min__gte=1), name="rc_k_range_min_gte_1"),
            models.CheckConstraint(check=models.Q(k_range_max__gt=models.F("k_range_min")), name="rc_k_range_max_gt_min"),
            models.CheckConstraint(check=models.Q(alpha__gte=0.001) & models.Q(alpha__lte=0.5), name="rc_alpha_range"),
            models.CheckConstraint(check=models.Q(vif_threshold__gte=1.0) & models.Q(vif_threshold__lte=100.0), name="rc_vif_threshold_range"),
            models.CheckConstraint(check=models.Q(regime_threshold__gte=0.0) & models.Q(regime_threshold__lte=1.0), name="rc_regime_threshold_range"),
            models.CheckConstraint(check=models.Q(regime_threshold_urban__gte=0.0) & models.Q(regime_threshold_urban__lte=1.0), name="rc_regime_threshold_urban_range"),
            models.CheckConstraint(check=models.Q(date_from__isnull=True) | models.Q(date_to__isnull=True) | models.Q(date_from__lte=models.F("date_to")), name="rc_date_from_lte_date_to"),
            models.UniqueConstraint(fields=["is_active"], condition=models.Q(is_active=True), name="rc_single_active_config"),
        ]

    def __str__(self):
        active = " [ACTIVE]" if self.is_active else ""
        return f"{self.name}{active}"

    def clean(self):
        errors = {}

        # 1. Voronoi + count_pop = bad (count=1 always, no variance)
        if (
            self.geometry_type == GeometryType.VORONOI
            and self.y_formula == YFormula.COUNT_POP
        ):
            errors["y_formula"] = (
                "Voronoi + count_pop is invalid: Voronoi cells are 1:1 with sightings, "
                "so sighting_count=1 always (no variance in Y)."
            )

        # 2. Voronoi + binary = bad (count>0 always, Y=1 everywhere, no variance)
        if (
            self.geometry_type == GeometryType.VORONOI
            and self.y_formula == YFormula.BINARY
        ):
            errors["y_formula"] = (
                "Voronoi + binary is invalid: Voronoi cells are 1:1 with sightings, "
                "so sighting_count>0 always, Y=1 everywhere (no variance)."
            )

        # 3. SAR/SEM/SDM + binary = bad (needs continuous Y)
        if (
            self.model_type
            in (
                ModelTypeChoice.SAR,
                ModelTypeChoice.SEM,
                ModelTypeChoice.SDM,
            )
            and self.y_formula == YFormula.BINARY
        ):
            errors["model_type"] = (
                f"{self.get_model_type_display()} requires continuous Y. "
                "Use probit or logit for binary Y, or change y_formula."
            )

        # 4. k_range_min >= k_range_max (guard against non-int body so a bad
        #    value is a clean ValidationError, not a swallowed TypeError)
        try:
            if int(self.k_range_min) >= int(self.k_range_max):
                errors["k_range_min"] = (
                    f"k_range_min ({self.k_range_min}) must be less than "
                    f"k_range_max ({self.k_range_max})."
                )
        except (TypeError, ValueError):
            errors["k_range_min"] = "k_range_min and k_range_max must be integers."

        # 5. date_from > date_to
        if self.date_from and self.date_to and self.date_from > self.date_to:
            errors["date_from"] = "date_from must be before date_to."

        # 6. active_predictors: must be a list of known predictor names only
        #    (mirrors the R allow-list in 03_osm_features.R and the DB layer).
        preds = self.active_predictors
        if not isinstance(preds, list):
            errors["active_predictors"] = (
                "active_predictors must be a JSON list of predictor names."
            )
        else:
            unknown = [
                p for p in preds
                if not isinstance(p, str) or p not in ALL_PREDICTORS
            ]
            if unknown:
                errors["active_predictors"] = (
                    f"Unknown predictor(s): {unknown}. "
                    f"Allowed: {', '.join(ALL_PREDICTORS)}."
                )
            else:
                # de-duplicate, preserve order (the UI toggle never sends dupes)
                seen = set()
                deduped = []
                for p in preds:
                    if p not in seen:
                        seen.add(p)
                        deduped.append(p)
                self.active_predictors = deduped

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Singleton-active: deactivate others when activating this one
        if self.is_active:
            ResearchConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(
                is_active=False
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def to_env_dict(self):
        """
        Convert all parameters to a flat dict of strings,
        suitable for passing as environment variables to R scripts.
        """
        env = {
            "RESEARCH_GEOMETRY_TYPE": self.geometry_type,
            "RESEARCH_POPULATION_METHOD": self.population_method,
            "RESEARCH_Y_FORMULA": self.y_formula,
            "RESEARCH_W_METHOD": self.w_method,
            "RESEARCH_K_RANGE_MIN": str(self.k_range_min),
            "RESEARCH_K_RANGE_MAX": str(self.k_range_max),
            "RESEARCH_MODEL_TYPE": self.model_type,
            "RESEARCH_ACTIVE_PREDICTORS": ",".join(self.active_predictors or []),
            "RESEARCH_RUN_MORAN": "1" if self.run_moran else "0",
            "RESEARCH_RUN_LM_TESTS": "1" if self.run_lm_tests else "0",
            "RESEARCH_RUN_LISA": "1" if self.run_lisa else "0",
            "RESEARCH_RUN_ETA": "1" if self.run_eta else "0",
            "RESEARCH_VIF_THRESHOLD": str(self.vif_threshold),
            "RESEARCH_ALPHA": str(self.alpha),
            "RESEARCH_SEED": str(self.seed),
            # Regime model
            "RESEARCH_USE_REGIME": "1" if self.use_regime_model else "0",
            "RESEARCH_REGIME_TYPE": self.regime_type,
            "RESEARCH_REGIME_THRESHOLD": str(self.regime_threshold),
            "RESEARCH_REGIME_THRESHOLD_URBAN": str(self.regime_threshold_urban),
        }
        if self.date_from:
            env["RESEARCH_DATE_FROM"] = self.date_from.isoformat()
        if self.date_to:
            env["RESEARCH_DATE_TO"] = self.date_to.isoformat()
        return env



class ResearchRun(models.Model):
    """
    One execution of the Research Pipeline.

    Stores a frozen snapshot of the config so results are reproducible
    even if the config is later modified.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    config = models.ForeignKey(
        ResearchConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
        help_text="Source config (may be null if config deleted)",
    )
    config_snapshot = models.JSONField(
        help_text="Frozen copy of config at the moment of run start",
    )

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=RunStatus.choices,
        default=RunStatus.PENDING,
    )

    n_sightings = models.PositiveIntegerField(
        help_text="Number of sightings included in this run",
    )
    n_cells = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of spatial units generated",
    )

    error_message = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Research Run"
        verbose_name_plural = "Research Runs"
        ordering = ["-started_at"]

    def __str__(self):
        cfg = self.config.name if self.config else "(deleted)"
        return f"Run {str(self.id)[:8]} [{self.status}] - {cfg}"



class ResearchStepLog(models.Model):
    """
    Per-step execution log for a Research Run.

    Each pipeline step (R script, Python calculation, SQL query)
    gets its own log row with timing, exit code, stdout/stderr.
    """

    run = models.ForeignKey(
        ResearchRun,
        on_delete=models.CASCADE,
        related_name="steps",
    )

    step_name = models.CharField(
        max_length=100,
        help_text="Human-readable step name (e.g. '01_generate_voronoi.R')",
    )
    step_order = models.PositiveIntegerField(
        help_text="Execution order (1-based)",
    )
    step_type = models.CharField(
        max_length=10,
        choices=StepType.choices,
    )

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    exit_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="Process exit code (0=success, 3=fallback, 137=OOM)",
    )
    status = models.CharField(
        max_length=10,
        choices=StepStatus.choices,
        default=StepStatus.RUNNING,
    )

    input_params = models.JSONField(
        default=dict,
        help_text="Parameters passed to this step",
    )
    output_stats = models.JSONField(
        null=True,
        blank=True,
        help_text="Statistics returned by this step",
    )

    stdout = models.TextField(blank=True, default="")
    stderr = models.TextField(blank=True, default="")

    errors = models.JSONField(
        default=list,
        help_text="List of error messages",
    )
    warnings = models.JSONField(
        default=list,
        help_text="List of warning messages",
    )

    class Meta:
        verbose_name = "Research Step Log"
        verbose_name_plural = "Research Step Logs"
        ordering = ["run", "step_order"]
        unique_together = ["run", "step_order"]

    def __str__(self):
        return f"Step {self.step_order}: {self.step_name} [{self.status}]"



class ResearchDiagnostics(models.Model):
    """
    Diagnostic test results for a Research Run.

    One-to-one with ResearchRun. Stores Moran's I, LM tests,
    model fit statistics, spatial parameters, and LISA summary.
    """

    run = models.OneToOneField(
        ResearchRun,
        on_delete=models.CASCADE,
        related_name="diagnostics",
        primary_key=True,
    )

    moran_i = models.FloatField(null=True, blank=True, help_text="Moran's I statistic")
    moran_expected = models.FloatField(
        null=True, blank=True, help_text="Expected Moran's I under H0"
    )
    moran_variance = models.FloatField(
        null=True, blank=True, help_text="Variance of Moran's I"
    )
    moran_z = models.FloatField(null=True, blank=True, help_text="Z-score")
    moran_p = models.FloatField(null=True, blank=True, help_text="p-value")

    lm_lag_stat = models.FloatField(
        null=True, blank=True, help_text="LM Lag test statistic"
    )
    lm_lag_p = models.FloatField(null=True, blank=True, help_text="LM Lag p-value")
    lm_error_stat = models.FloatField(
        null=True, blank=True, help_text="LM Error test statistic"
    )
    lm_error_p = models.FloatField(null=True, blank=True, help_text="LM Error p-value")
    rlm_lag_stat = models.FloatField(
        null=True, blank=True, help_text="Robust LM Lag statistic"
    )
    rlm_lag_p = models.FloatField(
        null=True, blank=True, help_text="Robust LM Lag p-value"
    )
    rlm_error_stat = models.FloatField(
        null=True, blank=True, help_text="Robust LM Error statistic"
    )
    rlm_error_p = models.FloatField(
        null=True, blank=True, help_text="Robust LM Error p-value"
    )

    model_selected = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Model actually selected (sar/sem/sdm/probit/logit)",
    )
    aic = models.FloatField(
        null=True, blank=True, help_text="Akaike Information Criterion"
    )
    log_likelihood = models.FloatField(null=True, blank=True)
    coefficients = models.JSONField(
        null=True,
        blank=True,
        help_text="Dict of predictor coefficients {name: {estimate, std_error, z, p}}",
    )
    r_squared = models.FloatField(null=True, blank=True, help_text="Pseudo R-squared")

    rho = models.FloatField(
        null=True, blank=True, help_text="SAR spatial lag parameter rho"
    )
    lambda_param = models.FloatField(
        null=True, blank=True, help_text="SEM spatial error parameter lambda"
    )

    lisa_hh_count = models.PositiveIntegerField(
        null=True, blank=True, help_text="High-High clusters"
    )
    lisa_ll_count = models.PositiveIntegerField(
        null=True, blank=True, help_text="Low-Low clusters"
    )
    lisa_hl_count = models.PositiveIntegerField(
        null=True, blank=True, help_text="High-Low outliers"
    )
    lisa_lh_count = models.PositiveIntegerField(
        null=True, blank=True, help_text="Low-High outliers"
    )
    lisa_ns_count = models.PositiveIntegerField(
        null=True, blank=True, help_text="Not significant"
    )

    vif_results = models.JSONField(
        null=True,
        blank=True,
        help_text="VIF per predictor {name: vif_value}",
    )
    predictors_dropped = models.JSONField(
        default=list,
        help_text="Predictors dropped due to VIF > threshold",
    )

    eta_h_emp = models.FloatField(
        null=True,
        blank=True,
        help_text="Empirical Shannon entropy: H = -Σ(s_i × ln(s_i))",
    )
    eta_h_max = models.FloatField(
        null=True,
        blank=True,
        help_text="Maximum entropy: H_max = ln(n)",
    )
    eta_h_rel = models.FloatField(
        null=True,
        blank=True,
        help_text="ETA (relative entropy): H_rel = H / H_max. Range [0,1]. ~1=uniform, <0.8=agglomeration",
    )

    k_selected = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Selected optimal k (for knn_aic method)",
    )
    mean_neighbors = models.FloatField(
        null=True,
        blank=True,
        help_text="Average number of neighbors per cell in W matrix",
    )

    # SAR/SDM only: β coefficients don't have simple marginal interpretation
    # due to spatial multiplier (I - ρW)⁻¹ - LeSage & Pace (2009)
    impacts = models.JSONField(
        null=True,
        blank=True,
        help_text="Spatial impacts: {direct: {...}, indirect: {...}, total: {...}} (SAR/SDM only)",
    )

    class Meta:
        verbose_name = "Research Diagnostics"
        verbose_name_plural = "Research Diagnostics"

    def __str__(self):
        model = self.model_selected or "N/A"
        aic_str = f"AIC={self.aic:.1f}" if self.aic else "no AIC"
        return f"Diagnostics [{model}] {aic_str}"
