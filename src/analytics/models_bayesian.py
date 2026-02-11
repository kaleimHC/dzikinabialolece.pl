"""
Bayesian Layer Models for Analytics app.
MASTER_SPEC v2.3 - Section I: Bayesian Integration Layer

These models define the schema for Bayesian analysis results.
R scripts (06_bayesian_ssm.R) write to these tables.
Django provides API/Admin access to read results.

Tables:
- analytics_prior_config: Prior configuration with audit trail
- analytics_bayesian_result: MCMC posterior summaries per grid cell
"""

import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

# Note: Use settings.AUTH_USER_MODEL for ForeignKey references
# to avoid AppRegistryNotReady errors at module load time


class PriorConfig(models.Model):
    """
    Prior configuration for Bayesian SSM.

    Stores hyperparameters with audit trail showing source values
    (H_rel from ETA, ARI from STS, bandwidth from GWR).

    ADR-011: Prior Elicitation Strategy
    - delta ~ Beta(kappa*H_rel, kappa*(1-H_rel))
    - rho ~ Beta(kappa*ARI, kappa*(1-ARI))
    - length_scale ~ LogNormal(log(h_opt), 0.3)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identification
    model_version = models.CharField(
        max_length=20, help_text="Version identifier for this prior configuration"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prior_configs",
    )

    # Parameter and distribution
    PARAMETER_CHOICES = [
        ("rho", "Persistence rho"),
        ("delta", "Diffusion delta"),
        ("kappa", "Concentration kappa"),
        ("length_scale", "Length-scale ell"),
    ]
    parameter_name = models.CharField(
        max_length=50,
        choices=PARAMETER_CHOICES,
        help_text="Which parameter this prior is for",
    )

    DIST_CHOICES = [
        ("beta", "Beta"),
        ("gamma", "Gamma"),
        ("half_cauchy", "Half-Cauchy"),
        ("lognormal", "Log-Normal"),
    ]
    dist_type = models.CharField(
        max_length=20, choices=DIST_CHOICES, help_text="Distribution type for the prior"
    )

    # Hyperparameters
    alpha_hyper = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        validators=[MinValueValidator(0.001)],
        help_text="Alpha (shape1) hyperparameter",
    )
    beta_hyper = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        validators=[MinValueValidator(0.001)],
        help_text="Beta (shape2) hyperparameter",
    )

    # Audit trail - source values from frequentist analysis
    source_h_rel = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="H_rel value from ETA (rescaled to N=1000)",
    )
    source_ari = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
        help_text="ARI value from STS (historical t-2 to t-1)",
    )
    source_bandwidth = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Bandwidth h_opt from GWR (meters)",
    )

    # Active flag
    is_active = models.BooleanField(
        default=True, help_text="Whether this prior config is currently active"
    )

    class Meta:
        db_table = "analytics_prior_config"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["model_version"]),
            models.Index(fields=["parameter_name"]),
            models.Index(fields=["is_active", "parameter_name"]),
        ]
        verbose_name = "Prior Configuration"
        verbose_name_plural = "Prior Configurations"

    def __str__(self):
        return f"{self.parameter_name} ~ {self.dist_type}({self.alpha_hyper}, {self.beta_hyper}) v{self.model_version}"

    def clean(self):
        super().clean()
        # Beta distribution requires alpha, beta > 0
        if self.dist_type == "beta":
            if self.alpha_hyper <= 0 or self.beta_hyper <= 0:
                raise ValidationError(
                    "Beta distribution requires alpha > 0 and beta > 0"
                )

        # Stationarity check for rho prior (ADR-011)
        # Expected rho = alpha / (alpha + beta)
        # If rho is too high (> 0.95), there's little room for delta
        # and model may become non-stationary (rho + delta >= 1.0)
        if self.parameter_name == "rho" and self.dist_type == "beta":
            alpha = float(self.alpha_hyper)
            beta = float(self.beta_hyper)
            expected_rho = alpha / (alpha + beta)
            if expected_rho > 0.95:
                raise ValidationError(
                    {
                        "alpha_hyper": (
                            f"Expected rho = {expected_rho:.3f} is too high (> 0.95). "
                            "This may lead to non-stationarity when combined with delta > 0.05. "
                            "Consider reducing alpha or increasing beta."
                        )
                    }
                )


class BayesianResult(models.Model):
    """
    Bayesian SSM results for each grid cell.

    Stores posterior summaries (mean, CI) and MCMC diagnostics (R-hat, ESS).
    Full posterior draws stored in /data/mcmc/{run_id}.rds for audit.

    ADR-013: Tiered Storage Strategy
    - Production/API: JSONB summary (this table)
    - Research/Audit: Full RDS files
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    execution = models.ForeignKey(
        "AnalyticsRun",  # Forward reference to existing model
        on_delete=models.CASCADE,
        related_name="bayesian_results",
        help_text="Which analytics run produced these results",
    )
    cell_id = models.IntegerField(help_text="Grid cell ID (FK to GridCell)")

    GRID_CHOICES = [
        ("square", "Square Grid (FAST)"),
        ("voronoi", "Voronoi Grid (PUB)"),
    ]
    grid_type = models.CharField(
        max_length=10,
        choices=GRID_CHOICES,
        help_text="Which grid type this result is for",
    )

    # Posterior summaries
    intensity_mean = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        help_text="E[lambda(s)] - posterior mean intensity",
    )
    intensity_median = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Median of posterior intensity",
    )
    ci_lower_95 = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        help_text="2.5th percentile (lower bound 95% CI)",
    )
    ci_upper_95 = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        help_text="97.5th percentile (upper bound 95% CI)",
    )
    ci_lower_50 = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="25th percentile (lower bound 50% CI)",
    )
    ci_upper_50 = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="75th percentile (upper bound 50% CI)",
    )
    prob_above_threshold = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="P(lambda > threshold) for alerting",
    )

    # MCMC diagnostics (CRITICAL for convergence validation)
    r_hat = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.9), MaxValueValidator(2.0)],
        help_text="Gelman-Rubin R-hat statistic. MUST be < 1.01",
    )
    ess_bulk = models.DecimalField(
        max_digits=10,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Effective Sample Size (bulk). SHOULD be > 400",
    )
    ess_tail = models.DecimalField(
        max_digits=10,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Effective Sample Size (tail). SHOULD be > 400",
    )

    # Model comparison metrics
    waic = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Widely Applicable Information Criterion",
    )
    loo_ic = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Leave-One-Out Information Criterion",
    )

    # Metadata
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_bayesian_result"
        ordering = ["-computed_at"]
        indexes = [
            models.Index(fields=["execution", "cell_id"]),
            models.Index(fields=["grid_type"]),
            models.Index(fields=["computed_at"]),
        ]
        # Partial indexes would be created via raw SQL migration:
        # CREATE INDEX idx_bayes_high_risk ON analytics_bayesian_result(prob_above_threshold)
        #     WHERE prob_above_threshold > 0.7;
        # CREATE INDEX idx_bayes_bad_convergence ON analytics_bayesian_result(r_hat)
        #     WHERE r_hat > 1.01;
        verbose_name = "Bayesian Result"
        verbose_name_plural = "Bayesian Results"

    def __str__(self):
        return (
            f"Bayes cell={self.cell_id} mean={self.intensity_mean} [{self.grid_type}]"
        )

    def clean(self):
        super().clean()
        # CI bounds must be ordered
        if self.ci_lower_95 is not None and self.ci_upper_95 is not None:
            if self.ci_lower_95 > self.ci_upper_95:
                raise ValidationError("ci_lower_95 must be <= ci_upper_95")
            if self.intensity_mean is not None:
                if not (self.ci_lower_95 <= self.intensity_mean <= self.ci_upper_95):
                    raise ValidationError("intensity_mean must be within 95% CI")

    @property
    def has_converged(self):
        """Check if MCMC has converged (R-hat < 1.01, ESS > 400)."""
        if self.r_hat is None or self.ess_bulk is None:
            return None
        return self.r_hat < 1.01 and self.ess_bulk > 400


# Trajectory model removed - friction costs feature deprecated
