"""
Migration: Add ETA fields according to NotebookLM methodology

New fields:
- eta_local: 1 - (tile_area / mean(tile_area)) - small tile = high local risk
- eta_weighted: eta_local * (1 - H_rel_global) - weighted by global clustering
- eta_contribution: -p_i*log(p_i)/H_max (legacy, for debugging)
- area_proportion: tile_area/total_area (legacy, for debugging)

Ref: docs/MIX-6_NOTEBOOKLM_RESPONSES.md
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sightings", "0005_fix_geometry_2180_multipolygon"),
    ]

    operations = [
        # Only add columns that don't exist yet
        # eta_contribution and area_proportion already exist from R script
        migrations.AddField(
            model_name="gridcell",
            name="eta_local",
            field=models.FloatField(
                blank=True,
                help_text="Local ETA: 1-(tile_area/mean_area), small tile=high risk",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="eta_weighted",
            field=models.FloatField(
                blank=True,
                help_text="Weighted ETA: eta_local * (1-H_rel), used in ensemble",
                null=True,
            ),
        ),
        # Sync existing columns to Django model (no DB change, just state)
        migrations.RunSQL(
            sql="SELECT 1;",  # No-op, column already exists
            reverse_sql="SELECT 1;",
            state_operations=[
                migrations.AddField(
                    model_name="gridcell",
                    name="eta_contribution",
                    field=models.FloatField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="gridcell",
                    name="area_proportion",
                    field=models.FloatField(blank=True, null=True),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="gridcell",
            name="eta_score",
            field=models.FloatField(
                default=0,
                help_text="ETA entropy score (normalized)",
            ),
        ),
    ]
