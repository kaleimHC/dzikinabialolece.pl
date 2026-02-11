# Generated manually for CLEANUP FAZA 3
# Removes hallucination columns: eta_local, eta_weighted
# Adds spatial_risk (SAR/SEM replacement for GWR)

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sightings", "0008_add_missing_gridcell_fields"),
    ]

    operations = [
        # Remove hallucination columns
        migrations.RemoveField(
            model_name="gridcell",
            name="eta_local",
        ),
        migrations.RemoveField(
            model_name="gridcell",
            name="eta_weighted",
        ),
        # Add spatial_risk (SAR/SEM model output)
        migrations.AddField(
            model_name="gridcell",
            name="spatial_risk",
            field=models.FloatField(
                blank=True, help_text="Spatial risk from SAR/SEM model (0-1)", null=True
            ),
        ),
    ]
