from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0007_research_config_checks"),
    ]

    operations = [
        migrations.AlterField(
            model_name="researchconfig",
            name="model_type",
            field=models.CharField(
                choices=[
                    ("auto", "Auto (SAR vs SEM by AIC)"),
                    ("sar", "SAR (Spatial Lag)"),
                    ("sem", "SEM (Spatial Error)"),
                    ("sdm", "SDM (Spatial Durbin)"),
                    ("probit", "Spatial Probit"),
                    ("logit", "Spatial Logit"),
                ],
                default="auto",
                help_text="Spatial model type (auto = SAR vs SEM by AIC; LM tests post-hoc only)",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="researchconfig",
            name="run_lm_tests",
            field=models.BooleanField(
                default=True,
                help_text="Run LM lag/error tests as post-hoc diagnostics (not used for model selection)",
            ),
        ),
    ]
