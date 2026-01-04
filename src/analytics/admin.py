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


