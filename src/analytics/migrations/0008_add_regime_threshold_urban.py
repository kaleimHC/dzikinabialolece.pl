# Generated manually for regime threshold urban field

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0007_remove_trajectory_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="researchconfig",
            name="regime_threshold_urban",
            field=models.FloatField(
                default=0.15,
                help_text="Building density threshold for urban regime (0-1)",
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="researchconfig",
            name="regime_type",
            field=models.CharField(
                choices=[
                    ("none", "Brak (jeden globalny model)"),
                    ("trinary", "Trinary (las/miasto/mixed)"),
                ],
                default="none",
                help_text="Type of regime classification",
                max_length=20,
            ),
        ),
    ]
