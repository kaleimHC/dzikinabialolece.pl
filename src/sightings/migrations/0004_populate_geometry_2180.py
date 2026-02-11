"""
Migration: Populate geometry_2180 and edge-to-edge distances

Transforms geometry from EPSG:4326 → EPSG:2180 and calculates
edge-to-edge distances to forest/water using ST_Distance (not centroid!)

References:
- Kopczewska/NotebookLM: "Minimum (C) - natywnie wspierane przez PostGIS/GEOS"
- spatialWarsaw: Uses EPSG:3857 but EPSG:2180 (PUWG 1992) is more accurate for Poland
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sightings", "0003_gridcell_spatialwarsaw_alignment"),
    ]

    operations = [
        # Step 1: Transform geometry to EPSG:2180
        # Use ST_Multi() to ensure MultiPolygon (barrier-aware grids may have holes)
        migrations.RunSQL(
            sql="""
                UPDATE sightings_gridcell
                SET geometry_2180 = ST_Multi(ST_Transform(geometry, 2180))
                WHERE geometry_2180 IS NULL;
            """,
            reverse_sql="""
                UPDATE sightings_gridcell
                SET geometry_2180 = NULL;
            """,
        ),
        # Step 2: Calculate edge-to-edge distance to forest
        # Uses KNN operator (<->) for performance with GiST index
        # ST_Distance on EPSG:2180 gives meters directly
        migrations.RunSQL(
            sql="""
                UPDATE sightings_gridcell g
                SET distance_to_forest = subq.dist
                FROM (
                    SELECT DISTINCT ON (gc.id)
                        gc.id,
                        ST_Distance(
                            ST_Transform(gc.geometry, 2180),
                            ST_Transform(f.geom, 2180)
                        ) as dist
                    FROM sightings_gridcell gc
                    CROSS JOIN LATERAL (
                        SELECT geom
                        FROM osm_forests
                        ORDER BY gc.geometry <-> geom
                        LIMIT 1
                    ) f
                ) subq
                WHERE g.id = subq.id
                  AND EXISTS (SELECT 1 FROM osm_forests LIMIT 1);
            """,
            reverse_sql="UPDATE sightings_gridcell SET distance_to_forest = NULL;",
        ),
        # Step 3: Calculate edge-to-edge distance to water
        migrations.RunSQL(
            sql="""
                UPDATE sightings_gridcell g
                SET distance_to_water = subq.dist
                FROM (
                    SELECT DISTINCT ON (gc.id)
                        gc.id,
                        ST_Distance(
                            ST_Transform(gc.geometry, 2180),
                            ST_Transform(w.geom, 2180)
                        ) as dist
                    FROM sightings_gridcell gc
                    CROSS JOIN LATERAL (
                        SELECT geom
                        FROM osm_water
                        ORDER BY gc.geometry <-> geom
                        LIMIT 1
                    ) w
                ) subq
                WHERE g.id = subq.id
                  AND EXISTS (SELECT 1 FROM osm_water LIMIT 1);
            """,
            reverse_sql="UPDATE sightings_gridcell SET distance_to_water = NULL;",
        ),
        # Step 4: Calculate road density (meters of road per km² cell area)
        migrations.RunSQL(
            sql="""
                UPDATE sightings_gridcell g
                SET road_density = subq.density
                FROM (
                    SELECT
                        gc.id,
                        COALESCE(
                            SUM(ST_Length(
                                ST_Intersection(
                                    ST_Transform(r.geom, 2180),
                                    ST_Transform(gc.geometry, 2180)
                                )
                            )) / NULLIF(ST_Area(ST_Transform(gc.geometry, 2180)) / 1000000, 0),
                            0
                        ) as density
                    FROM sightings_gridcell gc
                    LEFT JOIN osm_roads r ON ST_Intersects(gc.geometry, r.geom)
                    GROUP BY gc.id
                ) subq
                WHERE g.id = subq.id
                  AND EXISTS (SELECT 1 FROM osm_roads LIMIT 1);
            """,
            reverse_sql="UPDATE sightings_gridcell SET road_density = NULL;",
        ),
        # Step 5: Calculate building density (building footprint / cell area)
        migrations.RunSQL(
            sql="""
                UPDATE sightings_gridcell g
                SET building_density = subq.density
                FROM (
                    SELECT
                        gc.id,
                        COALESCE(
                            SUM(ST_Area(
                                ST_Intersection(
                                    ST_Transform(b.geom, 2180),
                                    ST_Transform(gc.geometry, 2180)
                                )
                            )) / NULLIF(ST_Area(ST_Transform(gc.geometry, 2180)), 0),
                            0
                        ) as density
                    FROM sightings_gridcell gc
                    LEFT JOIN osm_buildings b ON ST_Intersects(gc.geometry, b.geom)
                    GROUP BY gc.id
                ) subq
                WHERE g.id = subq.id
                  AND EXISTS (SELECT 1 FROM osm_buildings LIMIT 1);
            """,
            reverse_sql="UPDATE sightings_gridcell SET building_density = NULL;",
        ),
    ]
