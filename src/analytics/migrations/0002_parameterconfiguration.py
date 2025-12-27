from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParameterConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="Configuration profile name (e.g., 'production', 'quick_preview')", max_length=100, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=False, help_text="Only one configuration can be active")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Parameter Configuration",
                "verbose_name_plural": "Parameter Configurations",
                "db_table": "analytics_parameter_configuration",
                "ordering": ["-is_active", "-updated_at"],
            },
        ),
    ]
