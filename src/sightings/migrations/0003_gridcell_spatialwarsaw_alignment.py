"""
Migration: spatialWarsaw alignment v1.4

Adds fields for alignment with spatialWarsaw R package:
- geometry_2180: EPSG:2180 (PUWG 1992) for metric calculations
- distance_to_forest/water: edge-to-edge distances in meters
- road_density, building_density: spatial predictors
- sighting_density, ensemble_risk, eta_score, gwr_score, confidence

References:
- docs/WARSAWSPATIAL_ALIGNMENT.md
- docs/NOTEBOOKLM_RESPONSES.md (Kopczewska validation)
"""

from django.contrib.gis.db import models
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sightings", "0002_add_sighting_type"),
    ]

    operations = [
        # Geometry in EPSG:2180 for metric calculations
        # MultiPolygon to handle barrier-aware grids with holes
        migrations.AddField(
            model_name="gridcell",
            name="geometry_2180",
            field=models.MultiPolygonField(
                srid=2180,
                spatial_index=True,
                null=True,
                blank=True,
                help_text="Geometry in EPSG:2180 (PUWG 1992) for metric calculations",
            ),
        ),
        # Density and risk scores
        migrations.AddField(
            model_name="gridcell",
            name="sighting_density",
            field=models.FloatField(default=0, help_text="Sightings per km²"),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="ensemble_risk",
            field=models.FloatField(default=0, help_text="Final risk score 0-1"),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="eta_score",
            field=models.FloatField(default=0, help_text="ETA entropy score"),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="gwr_score",
            field=models.FloatField(default=0, help_text="GWR prediction score"),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="confidence",
            field=models.FloatField(default=0.2, help_text="Prediction confidence 0-1"),
        ),
        # Spatial predictors (spatialWarsaw alignment)
        migrations.AddField(
            model_name="gridcell",
            name="distance_to_forest",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text="Edge-to-edge distance to nearest forest (m), EPSG:2180",
            ),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="distance_to_water",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text="Edge-to-edge distance to nearest water body (m), EPSG:2180",
            ),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="road_density",
            field=models.FloatField(
                null=True, blank=True, help_text="Road density within cell (m/km²)"
            ),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="building_density",
            field=models.FloatField(
                null=True, blank=True, help_text="Building footprint ratio within cell"
            ),
        ),
        # Add index on ensemble_risk for heatmap queries
        migrations.AddIndex(
            model_name="gridcell",
            index=models.Index(
                fields=["ensemble_risk"], name="sightings_g_ensembl_idx"
            ),
        ),
    ]
