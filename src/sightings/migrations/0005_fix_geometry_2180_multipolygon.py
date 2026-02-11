"""
Migration: Fix geometry_2180 field type to match database

Syncs the model with the actual database state after manual intervention.
"""

from django.contrib.gis.db import models
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sightings", "0004_populate_geometry_2180"),
    ]

    operations = [
        # Rename index to match Django's expected naming
        migrations.RenameIndex(
            model_name="gridcell",
            new_name="sightings_g_ensembl_9f1258_idx",
            old_name="sightings_g_ensembl_idx",
        ),
        # Alter geometry_2180 from Polygon to MultiPolygon (already done in DB)
        migrations.AlterField(
            model_name="gridcell",
            name="geometry_2180",
            field=models.MultiPolygonField(
                blank=True,
                help_text="Edge-to-edge distance to nearest forest (m), EPSG:2180",
                null=True,
                srid=2180,
            ),
        ),
        # Sync status field default
        migrations.AlterField(
            model_name="sighting",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Oczekuje na weryfikację"),
                    ("verified", "Zweryfikowane"),
                    ("rejected", "Odrzucone"),
                    ("duplicate", "Duplikat"),
                ],
                db_index=True,
                default="verified",
                max_length=20,
            ),
        ),
    ]
