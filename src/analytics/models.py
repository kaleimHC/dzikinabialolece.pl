"""
Models for Analytics app.
MASTER_SPEC v2.2 Architecture
"""

from django.contrib.gis.db import models


class ModelPrediction(models.Model):
    """
    Prediction results from GWR/RF ensemble model.

    Stored per grid cell, updated weekly.
    """

    class ModelType(models.TextChoices):
        GWR = "gwr", "Geographically Weighted Regression"
        RF = "rf", "Random Forest"
        ENSEMBLE = "ensemble", "Ensemble (GWR + RF)"

    # Reference to grid cell
    grid_cell = models.ForeignKey(
        "sightings.GridCell", on_delete=models.CASCADE, related_name="predictions"
    )

    # Model metadata
    model_type = models.CharField(
        max_length=20, choices=ModelType.choices, default=ModelType.ENSEMBLE
    )
    model_version = models.CharField(max_length=50)

    # Prediction
    prediction_value = models.FloatField(
        help_text="Predicted encounter probability (0-1)"
    )
    confidence_lower = models.FloatField(null=True, blank=True)
    confidence_upper = models.FloatField(null=True, blank=True)

    # Temporal
    prediction_date = models.DateField(help_text="Date this prediction is valid for")
    created_at = models.DateTimeField(auto_now_add=True)

    # GWR-specific fields
    local_r_squared = models.FloatField(
        null=True, blank=True, help_text="Local R² from GWR"
    )
    bandwidth = models.FloatField(
        null=True, blank=True, help_text="GWR bandwidth in meters"
    )

    class Meta:
        ordering = ["-prediction_date", "grid_cell"]
        indexes = [
            models.Index(fields=["prediction_date", "model_type"]),
            models.Index(fields=["grid_cell", "prediction_date"]),
        ]
        unique_together = ["grid_cell", "model_type", "prediction_date"]

    def __str__(self):
        return f"{self.model_type} prediction for {self.grid_cell} on {self.prediction_date}"


class AnalyticsRun(models.Model):
    """
    Metadata for analytics pipeline runs.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    task_id = models.CharField(max_length=255, unique=True)
    task_name = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    # Results
    result_summary = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Input parameters
    parameters = models.JSONField(default=dict)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.task_name} ({self.status}) - {self.started_at.date()}"


# Import Bayesian models (MASTER_SPEC v2.3)
