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
    """

    grid_id = models.CharField(max_length=20, unique=True)
    geometry = models.PolygonField(srid=4326, spatial_index=True)
    centroid = models.PointField(srid=4326, null=True, blank=True)
    district = models.CharField(max_length=100, blank=True)

    sighting_count = models.PositiveIntegerField(default=0)
    last_sighting_at = models.DateTimeField(null=True, blank=True)

    sighting_density = models.FloatField(default=0, help_text="Sightings per km²")
    ensemble_risk = models.FloatField(default=0, help_text="Final risk score 0-1")

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
