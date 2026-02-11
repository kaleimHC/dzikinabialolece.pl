"""
Admin configuration for Sightings app.
Uses OSMGeoAdmin for map-based editing.
"""

from django.contrib.gis import admin
from .models import Sighting, GridCell, WarsawBoundary


@admin.register(Sighting)
class SightingAdmin(admin.GISModelAdmin):
    """Admin for Sighting model with map widget."""

    list_display = [
        "id",
        "observed_at",
        "status",
        "boar_count",
        "district_name",
        "created_at",
    ]
    list_filter = ["status", "boar_count", "observed_at"]
    search_fields = ["description", "grid_cell__district"]
    date_hierarchy = "observed_at"
    readonly_fields = ["ip_hash", "created_at", "updated_at"]

    # Map settings
    gis_widget_kwargs = {
        "attrs": {
            "default_lon": 21.0,
            "default_lat": 52.23,
            "default_zoom": 11,
        }
    }

    def district_name(self, obj):
        return obj.grid_cell.district if obj.grid_cell else "-"

    district_name.short_description = "Dzielnica"

    actions = ["approve_sightings", "reject_sightings"]

    @admin.action(description="Zatwierdź wybrane zgłoszenia")
    def approve_sightings(self, request, queryset):
        updated = queryset.update(status=Sighting.Status.VERIFIED)
        self.message_user(request, f"Zatwierdzono {updated} zgłoszeń.")

    @admin.action(description="Odrzuć wybrane zgłoszenia")
    def reject_sightings(self, request, queryset):
        updated = queryset.update(status=Sighting.Status.REJECTED)
        self.message_user(request, f"Odrzucono {updated} zgłoszeń.")


@admin.register(GridCell)
class GridCellAdmin(admin.GISModelAdmin):
    """Admin for GridCell model."""

    list_display = ["grid_id", "district", "sighting_count", "last_sighting_at"]
    list_filter = ["district"]
    search_fields = ["grid_id", "district"]
    readonly_fields = ["sighting_count", "last_sighting_at"]


@admin.register(WarsawBoundary)
class WarsawBoundaryAdmin(admin.GISModelAdmin):
    """Admin for Warsaw boundary polygon."""

    list_display = ["name"]
