from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0009_add_eta_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="researchdiagnostics",
            name="k_selected",
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                help_text="Selected optimal k (for knn_aic method)",
            ),
        ),
        migrations.AddField(
            model_name="researchdiagnostics",
            name="mean_neighbors",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text="Average number of neighbors per cell in W matrix",
            ),
        ),
    ]
