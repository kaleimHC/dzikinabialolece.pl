"""
Migration: Apply eta_score → area_rank_score rename to remaining tables.

Migration 0012 was marked applied but the SQL failed for sightings_gridcell
and sightings_gridcell_square (research_grid_250m doesn't exist; transaction
rolled back; migration was --faked). This migration corrects the state.

DB operations are intentionally empty — both tables were renamed manually
via direct ALTER TABLE on 2026-06-11. SeparateDatabaseAndState records the
rename in Django migration state so ORM and makemigrations stay consistent.

Tables fixed:
- sightings_gridcell (Django ORM model GridCell)
- sightings_gridcell_square (raw SQL, no model — no state_operation needed)
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sightings", "0012_rename_eta_score_to_area_rank_score"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameField(
                    model_name="gridcell",
                    old_name="eta_score",
                    new_name="area_rank_score",
                ),
            ],
        ),
    ]
