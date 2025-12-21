"""
GeoDjango Models for Sightings app.
"""

from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.utils import timezone


class Sighting(models.Model):
    """
    Wild boar sighting report.

    Constraint: Location must be within Warsaw administrative boundaries.
    Privacy: IP hashed with HMAC-SHA256, retained 3-7 days.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Oczekuje na weryfikację"
        VERIFIED = "verified", "Zweryfikowane"
        REJECTED = "rejected", "Odrzucone"
        DUPLICATE = "duplicate", "Duplikat"

    class BoarCount(models.TextChoices):
        SINGLE = "1", "Pojedynczy"
        FEW = "2-3", "2-3 osobniki"
        GROUP = "4-10", "4-10 osobników"
        HERD = "10+", "Ponad 10"

    class SightingType(models.TextChoices):
        ENCOUNTER = "encounter", "Spotkanie"
        RYJOWISKO = "ryjowisko", "Ryjowisko"

    location = models.PointField(
        srid=4326,
        spatial_index=True,
        help_text="Lokalizacja zgłoszenia (WGS84)",
    )

    observed_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Data i czas obserwacji",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.VERIFIED,
        db_index=True,
    )

    boar_count = models.CharField(
        max_length=10,
        choices=BoarCount.choices,
        default=BoarCount.SINGLE,
        help_text="Szacunkowa liczba dzików",
    )
    sighting_type = models.CharField(
        max_length=20,
        choices=SightingType.choices,
        default=SightingType.ENCOUNTER,
        help_text="Typ zgłoszenia",
    )
    description = models.TextField(
        blank=True, max_length=1000, help_text="Opcjonalny opis"
    )

    # Privacy (GDPR compliant)
    ip_hash = models.CharField(
        max_length=64, blank=True, help_text="HMAC-SHA256 hash of IP for anti-spam"
    )

    grid_cell = models.ForeignKey(
        "GridCell",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sightings",
    )

    class Meta:
        ordering = ["-observed_at"]
        indexes = [
            models.Index(fields=["status", "observed_at"]),
        ]

    def __str__(self):
        return f"Sighting #{self.pk} at {self.observed_at.date()}"


class GridCell(models.Model):
    """
    Static 1km² grid cell for aggregation.

    Required by Polish Hunting Law: aggregation must be ≥1 km².
    Pre-populated, not user-generated.

    spatialWarsaw alignment (v1.4):
    - geometry_2180: EPSG:2180 (PUWG 1992) for metric calculations
    - distance_to_water: edge-to-edge (ST_Distance), not centroid
    - Row-standardized weights for smoothing
    """

    grid_id = models.CharField(max_length=20, unique=True)
    geometry = models.PolygonField(srid=4326, spatial_index=True)

    # Geometry in EPSG:2180 (PUWG 1992) for metric calculations
    # spatialWarsaw: "Użyć układu EPSG:2180 (metryczny)!"
    # Note: MultiPolygon to handle barrier-aware grids with holes
    geometry_2180 = models.MultiPolygonField(
        srid=2180, spatial_index=True, null=True, blank=True
    )

    centroid = models.PointField(srid=4326, null=True, blank=True)
    district = models.CharField(max_length=100, blank=True)

    # Statistics (denormalized for performance)
    sighting_count = models.PositiveIntegerField(default=0)
    last_sighting_at = models.DateTimeField(null=True, blank=True)

    sighting_density = models.FloatField(default=0, help_text="Sightings per km²")
    ensemble_risk = models.FloatField(default=0, help_text="Final risk score 0-1")
    area_rank_score = models.FloatField(
        default=0, help_text="Area-based rank score (1 - percentile_rank(area))"
    )
    gwr_score = models.FloatField(default=0, help_text="GWR prediction score")
    confidence = models.FloatField(default=0.2, help_text="Prediction confidence 0-1")

    # Proximity factor - tłumienie ryzyka dla komórek daleko od obserwacji
    # proximity_weight = 1 / (1 + dist_to_nearest_sighting / 200)
    proximity_weight = models.FloatField(
        default=1.0,
        help_text="Proximity weight: 1/(1+d/200m), dampens risk far from sightings",
    )

    # Spatial risk from SAR/SEM models (spatialWarsaw methodology)
    # Replaces old GWR approach; eta_local/eta_weighted removed (never computed in production)
    spatial_risk = models.FloatField(
        null=True, blank=True, help_text="Spatial risk from SAR/SEM model (0-1)"
    )
    eta_contribution = models.FloatField(
        null=True,
        blank=True,
        help_text="Contribution to global entropy: -p_i*log(p_i)/H_max",
    )
    area_proportion = models.FloatField(
        null=True, blank=True, help_text="Tile area proportion: tile_area/total_area"
    )

    # Spatial predictors (spatialWarsaw alignment)
    # Distances in meters (EPSG:2180), edge-to-edge (not centroid!)
    distance_to_water = models.FloatField(
        null=True,
        blank=True,
        help_text="Edge-to-edge distance to nearest water body (m), EPSG:2180",
    )
    road_density = models.FloatField(
        null=True, blank=True, help_text="Road density within cell (m/km²)"
    )
    building_density = models.FloatField(
        null=True, blank=True, help_text="Building footprint ratio within cell"
    )

    class Meta:
        indexes = [
            models.Index(fields=["district"]),
            models.Index(fields=["ensemble_risk"]),
        ]

    def __str__(self):
        return f"Grid {self.grid_id}"


class WarsawBoundary(models.Model):
    """
    Warsaw administrative boundary for ST_Contains validation.
    Single row table.
    """

    name = models.CharField(max_length=100, default="Warszawa")
    geometry = models.MultiPolygonField(srid=4326, spatial_index=True)

    class Meta:
        verbose_name_plural = "Warsaw Boundaries"

    def __str__(self):
        return self.name

    @classmethod
    def contains_point(cls, point: Point) -> bool:
        """Check if point is within Warsaw boundaries."""
        try:
            boundary = cls.objects.first()
            if boundary is None:
                return True
            return boundary.geometry.contains(point)
        except Exception:
            return True
