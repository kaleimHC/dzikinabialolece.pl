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
