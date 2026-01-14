"""
DB-level defense-in-depth CHECK constraints for Sighting.

Adds CHECK constraints so the database itself rejects any row no
pre-programmed button (or sample loader) could emit, even when the
SightingCreateSerializer is bypassed (raw SQL, Django admin, mgmt command,
a future ModelSerializer). Values are verbatim from the model TextChoices;
verified against the loaded sample (no row violates any constraint).

- enum CHECKs: status / boar_count / sighting_type
- description length <= 1000 (model max_length is form-only, not DB-enforced)
- Warsaw bbox on location: rejects points outside the serializer's coarse
  lat/lng envelope. Defense-in-depth for non-serializer inserts (raw SQL,
  admin, mgmt command).
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("sightings", "0005_research_grid_indexes"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="sighting",
            constraint=models.CheckConstraint(
                check=Q(status__in=["pending", "verified", "rejected", "duplicate"]),
                name="sighting_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="sighting",
            constraint=models.CheckConstraint(
                check=Q(boar_count__in=["1", "2-3", "4-10", "10+"]),
                name="sighting_boar_count_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="sighting",
            constraint=models.CheckConstraint(
                check=Q(sighting_type__in=["encounter", "ryjowisko"]),
                name="sighting_type_valid",
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE sightings_sighting ADD CONSTRAINT sighting_description_len "
                "CHECK (char_length(description) <= 1000);"
            ),
            reverse_sql="ALTER TABLE sightings_sighting DROP CONSTRAINT IF EXISTS sighting_description_len;",
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE sightings_sighting ADD CONSTRAINT sighting_location_warsaw_bbox "
                "CHECK (ST_X(location::geometry) BETWEEN 20.5 AND 21.5 "
                "AND ST_Y(location::geometry) BETWEEN 51.9 AND 52.5);"
            ),
            reverse_sql="ALTER TABLE sightings_sighting DROP CONSTRAINT IF EXISTS sighting_location_warsaw_bbox;",
        ),
    ]
