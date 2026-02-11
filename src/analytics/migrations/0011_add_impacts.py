# Generated migration for impacts field
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add impacts JSONField to ResearchDiagnostics.

    Stores spatial impacts (direct/indirect/total) for SAR/SDM models.
    Reference: LeSage & Pace (2009) "Introduction to Spatial Econometrics"
    """

    dependencies = [
        ("analytics", "0010_add_w_metrics"),
    ]

    operations = [
        migrations.AddField(
            model_name="researchdiagnostics",
            name="impacts",
            field=models.JSONField(
                blank=True,
                null=True,
                help_text="Spatial impacts: {direct: {...}, indirect: {...}, total: {...}} (SAR/SDM only)",
            ),
        ),
    ]
