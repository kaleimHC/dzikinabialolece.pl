# Generated manually - Add missing GridCell fields

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add missing GridCell fields that exist in model but not in database."""

    dependencies = [
        ("sightings", "0007_create_isolated_grid_tables"),
    ]

    operations = [
        migrations.AddField(
            model_name="gridcell",
            name="proximity_weight",
            field=models.FloatField(
                default=0.0,
                help_text="Calculated weight based on proximity to observations",
            ),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="eta_contribution",
            field=models.FloatField(default=0.0, help_text="ETA contribution to cell"),
        ),
        migrations.AddField(
            model_name="gridcell",
            name="area_proportion",
            field=models.FloatField(
                default=0.0, help_text="Proportion of cell area within boundary"
            ),
        ),
    ]
