import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sightings", "0003_grid_tables"),
    ]

    operations = [
        migrations.CreateModel(
            name="OsmBuilding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("osm_id", models.BigIntegerField(blank=True, null=True)),
                ("building_type", models.TextField(blank=True, null=True)),
                ("geom", django.contrib.gis.db.models.fields.GeometryField(null=True, srid=4326)),
                ("fetched_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "osm_buildings", "managed": False},
        ),
        migrations.CreateModel(
            name="OsmBarrier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("osm_id", models.BigIntegerField(blank=True, null=True)),
                ("barrier_type", models.TextField(blank=True, null=True)),
                ("permeability", models.FloatField(blank=True, null=True)),
                ("geom", django.contrib.gis.db.models.fields.GeometryField(null=True, srid=4326)),
            ],
            options={"db_table": "osm_barriers", "managed": False},
        ),
        migrations.CreateModel(
            name="OsmForest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("osm_id", models.BigIntegerField(blank=True, null=True)),
                ("name", models.TextField(blank=True, null=True)),
                ("geom", django.contrib.gis.db.models.fields.GeometryField(null=True, srid=4326)),
                ("fetched_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "osm_forests", "managed": False},
        ),
        migrations.CreateModel(
            name="OsmRoad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("osm_id", models.BigIntegerField(blank=True, null=True)),
                ("highway", models.TextField(blank=True, null=True)),
                ("name", models.TextField(blank=True, null=True)),
                ("geom", django.contrib.gis.db.models.fields.GeometryField(null=True, srid=4326)),
                ("fetched_at", models.DateTimeField(blank=True, null=True)),
                ("permeability", models.FloatField(default=0.5)),
            ],
            options={"db_table": "osm_roads", "managed": False},
        ),
        migrations.CreateModel(
            name="OsmWater",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("osm_id", models.BigIntegerField(blank=True, null=True)),
                ("name", models.TextField(blank=True, null=True)),
                ("waterway", models.TextField(blank=True, null=True)),
                ("geom", django.contrib.gis.db.models.fields.GeometryField(null=True, srid=4326)),
                ("fetched_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "osm_water", "managed": False},
        ),
    ]
