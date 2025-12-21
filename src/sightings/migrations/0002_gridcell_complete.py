"""
Migration: GridCell complete — all spatial fields + geometry_2180 population.

Adds spatial predictor fields and ensemble score fields.
RunSQL populates geometry_2180 from geometry (EPSG:4326 → EPSG:2180).
"""

from django.contrib.gis.db.backends.postgis.operations import PostGISOperations
from django.db import migrations, models
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):
    dependencies = [
        ("sightings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="gridcell",
            name="geometry_2180",
            field=django.contrib.gis.db.models.fields.MultiPolygonField(
                blank=True, null=True, srid=2180
            ),
        ),
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
            name="area_rank_score",
            field=models.FloatField(
                default=0,
                help_text="Area-based rank score (1 - percentile_rank(area))",
            ),
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
        migrations.AddField(
            model_name="gridcell",
            name="proximity_weight",
            field=models.FloatField(
                default=1.0,
                help_text="Proximity weight: 1/(1+d/200m), dampens risk far from sightings",
            ),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="spatial_risk",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text="Spatial risk from SAR/SEM model (0-1)",
            ),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="eta_contribution",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text="Contribution to global entropy: -p_i*log(p_i)/H_max",
            ),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="area_proportion",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text="Tile area proportion: tile_area/total_area",
            ),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="distance_to_water",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text="Edge-to-edge distance to nearest water body (m), EPSG:2180",
            ),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="road_density",
            field=models.FloatField(
                blank=True, null=True, help_text="Road density within cell (m/km²)"
            ),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="building_density",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text="Building footprint ratio within cell",
            ),
        ),
        migrations.AddIndex(
            model_name="gridcell",
            index=models.Index(
                fields=["ensemble_risk"], name="sightings_g_ensembl_9f1258_idx"
            ),
        ),
        # Populate geometry_2180 from existing geometry (EPSG:4326 → EPSG:2180)
        migrations.RunSQL(
            sql="""
                UPDATE sightings_gridcell
                SET geometry_2180 = ST_Multi(ST_Transform(geometry, 2180))
                WHERE geometry_2180 IS NULL;
            """,
            reverse_sql="""
                UPDATE sightings_gridcell
                SET geometry_2180 = NULL;
            """,
        ),
    ]
