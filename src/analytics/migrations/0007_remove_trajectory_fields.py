# Generated manually to remove trajectory/friction costs feature

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0006_add_regime_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="parameterconfiguration",
            name="trajectories_enabled",
        ),
        migrations.RemoveField(
            model_name="parameterconfiguration",
            name="trajectory_count",
        ),
        # Note: Trajectory model table was already removed in a previous cleanup
    ]
