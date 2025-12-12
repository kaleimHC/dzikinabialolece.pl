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

    # Grid identifier
    grid_id = models.CharField(max_length=20, unique=True)

    # Geometry (polygon) - WGS84 for storage/display
    geometry = models.PolygonField(srid=4326, spatial_index=True)

    # Geometry in EPSG:2180 (PUWG 1992) for metric calculations
    # spatialWarsaw: "Użyć układu EPSG:2180 (metryczny)!"
    # Note: MultiPolygon to handle barrier-aware grids with holes
    geometry_2180 = models.MultiPolygonField(srid=2180, spatial_index=True, null=True, blank=True)

    # Centroid (for display)
    centroid = models.PointField(srid=4326, null=True, blank=True)

    # District reference
    district = models.CharField(max_length=100, blank=True)

    # Statistics (denormalized for performance)
    sighting_count = models.PositiveIntegerField(default=0)
    last_sighting_at = models.DateTimeField(null=True, blank=True)

    # Density and risk scores (v1.2+)
    sighting_density = models.FloatField(default=0, help_text='Sightings per km²')
    ensemble_risk = models.FloatField(default=0, help_text='Final risk score 0-1')
    area_rank_score = models.FloatField(default=0, help_text='Area-based rank score (1 - percentile_rank(area))')
    gwr_score = models.FloatField(default=0, help_text='GWR prediction score')
    confidence = models.FloatField(default=0.2, help_text='Prediction confidence 0-1')

    # Proximity factor (v1.6) - tłumienie ryzyka dla komórek daleko od obserwacji
    # proximity_weight = 1 / (1 + dist_to_nearest_sighting / 200)
    proximity_weight = models.FloatField(
        default=1.0,
        help_text='Proximity weight: 1/(1+d/200m), dampens risk far from sightings'
    )

    # Spatial risk from SAR/SEM models (spatialWarsaw methodology)
    # Replaces old GWR approach; eta_local/eta_weighted were hallucinations - REMOVED
    spatial_risk = models.FloatField(
        null=True, blank=True,
        help_text='Spatial risk from SAR/SEM model (0-1)'
    )
    # Raw values for debugging
    eta_contribution = models.FloatField(
        null=True, blank=True,
        help_text='Contribution to global entropy: -p_i*log(p_i)/H_max'
    )
    area_proportion = models.FloatField(
        null=True, blank=True,
        help_text='Tile area proportion: tile_area/total_area'
    )

    # Spatial predictors (spatialWarsaw alignment)
    # Distances in meters (EPSG:2180), edge-to-edge (not centroid!)
    distance_to_water = models.FloatField(
        null=True, blank=True,
        help_text='Edge-to-edge distance to nearest water body (m), EPSG:2180'
    )
    road_density = models.FloatField(
        null=True, blank=True,
        help_text='Road density within cell (m/km²)'
    )
    building_density = models.FloatField(
        null=True, blank=True,
        help_text='Building footprint ratio within cell'
    )

    class Meta:
        indexes = [
            models.Index(fields=['district']),
            models.Index(fields=['ensemble_risk']),
        ]

    def __str__(self):
        return f"Grid {self.grid_id}"


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
# OSM TABLES (managed=False - tabele istnieją, tylko dokumentacja)
# OSM models below (managed=False): retained for migration history only.
# Not registered in admin.py (see sightings/admin.py and analytics/admin.py for
# active registrations). All OSM API views use raw SQL (connection.cursor())
# in analytics/views.py — the ORM is intentionally bypassed for these layers.
# =============================================================================

class OsmForest(models.Model):
    """Lasy z OpenStreetMap - preferowane siedlisko dzików"""
    osm_id = models.BigIntegerField(null=True, blank=True)
    name = models.TextField(null=True, blank=True)
    geom = models.GeometryField(srid=4326, null=True)
    fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'osm_forests'


class OsmWater(models.Model):
    """Wody z OpenStreetMap - zbiorniki i cieki wodne"""
    osm_id = models.BigIntegerField(null=True, blank=True)
    name = models.TextField(null=True, blank=True)
    waterway = models.TextField(null=True, blank=True)
    geom = models.GeometryField(srid=4326, null=True)
    fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'osm_water'


class OsmRoad(models.Model):
    """Drogi z OpenStreetMap - sieć drogowa"""
    osm_id = models.BigIntegerField(null=True, blank=True)
    highway = models.TextField(null=True, blank=True)
    name = models.TextField(null=True, blank=True)
    geom = models.GeometryField(srid=4326, null=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    permeability = models.FloatField(default=0.5)

    class Meta:
        managed = False
        db_table = 'osm_roads'


class OsmBuilding(models.Model):
    """Budynki z OpenStreetMap - zabudowa"""
    osm_id = models.BigIntegerField(null=True, blank=True)
    building_type = models.TextField(null=True, blank=True)
    geom = models.GeometryField(srid=4326, null=True)
    fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'osm_buildings'


class OsmBarrier(models.Model):
    """Bariery z OpenStreetMap - ogrodzenia, mury"""
    osm_id = models.BigIntegerField(null=True, blank=True)
    barrier_type = models.TextField(null=True, blank=True)
    permeability = models.FloatField(null=True, blank=True)
    geom = models.GeometryField(srid=4326, null=True)  # LineString

    class Meta:
        managed = False
        db_table = 'osm_barriers'
