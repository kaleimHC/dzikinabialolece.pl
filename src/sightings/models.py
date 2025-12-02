"""
GeoDjango Models for Sightings app.
MASTER_SPEC v2.2 Architecture

CRITICAL INDEXES (to add via migrations):
- SPGIST for location (10-30% faster than GIST for points)
- BRIN for observed_at (12.8x faster for range queries)
- Partial index for status='pending'
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
        PENDING = 'pending', 'Oczekuje na weryfikację'
        VERIFIED = 'verified', 'Zweryfikowane'
        REJECTED = 'rejected', 'Odrzucone'
        DUPLICATE = 'duplicate', 'Duplikat'
    
    class BoarCount(models.TextChoices):
        SINGLE = '1', 'Pojedynczy'
        FEW = '2-3', '2-3 osobniki'
        GROUP = '4-10', '4-10 osobników'
        HERD = '10+', 'Ponad 10'

    class SightingType(models.TextChoices):
        ENCOUNTER = 'encounter', 'Spotkanie'
        RYJOWISKO = 'ryjowisko', 'Ryjowisko'
    
    # Geometry (SRID 4326 = WGS84)
    location = models.PointField(
        srid=4326,
        spatial_index=True,  # Creates GIST index by default
        help_text='Lokalizacja zgłoszenia (WGS84)'
    )
    
    # Temporal
    observed_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,  # Standard B-tree; consider BRIN in production
        help_text='Data i czas obserwacji'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Moderation
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.VERIFIED,  # TODO: PENDING when moderation ready
        db_index=True
    )
    
    # Details
    boar_count = models.CharField(
        max_length=10,
        choices=BoarCount.choices,
        default=BoarCount.SINGLE,
        help_text='Szacunkowa liczba dzików'
    )
    sighting_type = models.CharField(
        max_length=20,
        choices=SightingType.choices,
        default=SightingType.ENCOUNTER,
        help_text='Typ zgłoszenia'
    )
    description = models.TextField(
        blank=True,
        max_length=1000,
        help_text='Opcjonalny opis'
    )
    
    # Privacy (GDPR compliant)
    ip_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text='HMAC-SHA256 hash of IP for anti-spam'
    )
    
    # Foreign key to grid cell (for aggregation)
    grid_cell = models.ForeignKey(
        'GridCell',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sightings'
    )
    
    class Meta:
        ordering = ['-observed_at']
        indexes = [
            # Composite index for common queries
            models.Index(fields=['status', 'observed_at']),
            # NOTE: SPGIST and BRIN indexes should be added via raw SQL migration:
            # CREATE INDEX idx_sightings_location_spgist ON sightings_sighting USING SPGIST (location);
            # CREATE INDEX idx_sightings_observed_at_brin ON sightings_sighting USING BRIN (observed_at);
        ]
    
    def __str__(self):
        return f"Sighting #{self.pk} at {self.observed_at.date()}"


class WarsawBoundary(models.Model):
    """
    Warsaw administrative boundary for ST_Contains validation.
    Single row table.
    """
    
    name = models.CharField(max_length=100, default='Warszawa')
    geometry = models.MultiPolygonField(srid=4326, spatial_index=True)
    
    class Meta:
        verbose_name_plural = 'Warsaw Boundaries'
    
    def __str__(self):
        return self.name
    
    @classmethod
    def contains_point(cls, point: Point) -> bool:
        """Check if point is within Warsaw boundaries."""
        try:
            boundary = cls.objects.first()
            if boundary:
                return boundary.geometry.contains(point)
            return True  # Allow if no boundary defined (dev mode)
        except Exception:
            return True  # Graceful degradation


# =============================================================================
