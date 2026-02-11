from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0008_add_regime_threshold_urban"),
    ]

    operations = [
        migrations.AddField(
            model_name="researchdiagnostics",
            name="eta_h_emp",
            field=models.FloatField(
                blank=True,
                help_text="Empirical Shannon entropy: H = -Σ(s_i × ln(s_i))",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="researchdiagnostics",
            name="eta_h_max",
            field=models.FloatField(
                blank=True,
                help_text="Maximum entropy: H_max = ln(n)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="researchdiagnostics",
            name="eta_h_rel",
            field=models.FloatField(
                blank=True,
                help_text="ETA (relative entropy): H_rel = H / H_max. Range [0,1]. ~1=uniform, <0.8=agglomeration",
                null=True,
            ),
        ),
    ]
