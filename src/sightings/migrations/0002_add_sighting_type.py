from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sightings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sighting",
            name="sighting_type",
            field=models.CharField(
                choices=[("encounter", "Spotkanie"), ("ryjowisko", "Ryjowisko")],
                default="encounter",
                help_text="Typ zgłoszenia",
                max_length=20,
            ),
        ),
    ]
