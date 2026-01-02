#!/usr/bin/env python
"""
Setup script for creating barrier-aware grid.
Run after OSM data is loaded.

Usage:
    docker exec -i dziki-api python scripts/setup_grid.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dziki.settings')
django.setup()

from django.db import connection


def create_boundaries():
    """Create Białołęka boundary from OSM."""
    print("Creating boundaries...")
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO boundaries (name, geom)
            SELECT 'bialoleka', way
            FROM planet_osm_polygon
            WHERE boundary = 'administrative'
              AND admin_level = '9'
              AND name = 'Białołęka'
            ON CONFLICT (name) DO UPDATE SET geom = EXCLUDED.geom;
        """)
        print(f"  Boundaries: {cursor.rowcount} rows")


def create_grid():
    """Create 100x100m grid with buildings subtracted.

    Writes to: sightings_gridcell_square (FAST mode table)
    """
    print("Creating barrier-aware SQUARE grid...")

    with connection.cursor() as cursor:
        # Clear existing square grid
        cursor.execute("TRUNCATE TABLE sightings_gridcell_square RESTART IDENTITY;")

        # Create grid within Białołęka, subtract buildings
        cursor.execute("""
            WITH bialoleka AS (
                SELECT geom FROM boundaries WHERE name = 'bialoleka'
            ),
            raw_grid AS (
                SELECT
                    ROW_NUMBER() OVER () as id,
                    ST_SetSRID(ST_MakeEnvelope(x, y, x + 0.001, y + 0.001, 4326), 4326) as geom
                FROM generate_series(20.92, 21.09, 0.001) x,
                     generate_series(52.28, 52.37, 0.001) y
            ),
            grid_in_bialoleka AS (
                SELECT g.id, ST_Intersection(g.geom, b.geom) as geom
                FROM raw_grid g, bialoleka b
                WHERE ST_Intersects(g.geom, b.geom)
            ),
            buildings_union AS (
                SELECT ST_Union(geom) as geom FROM osm_buildings
            ),
            grid_no_buildings AS (
                SELECT
                    g.id,
                    CASE
                        WHEN ST_Intersects(g.geom, b.geom)
                        THEN ST_Difference(g.geom, b.geom)
                        ELSE g.geom
                    END as geom
                FROM grid_in_bialoleka g, buildings_union b
            )
            INSERT INTO sightings_gridcell_square (grid_id, geometry, sighting_count, district, centroid)
            SELECT
                'GRID-' || id as grid_id,
                geom as geometry,
                0 as sighting_count,
                'Białołęka' as district,
                ST_Centroid(geom) as centroid
            FROM grid_no_buildings
            WHERE NOT ST_IsEmpty(geom) AND ST_Area(geom::geography) > 50;
        """)

        cursor.execute("SELECT COUNT(*) FROM sightings_gridcell_square;")
        count = cursor.fetchone()[0]
        print(f"  Square grid cells created: {count}")


def assign_sightings():
    """Count sightings per square grid cell using spatial join.

    Uses: sightings_gridcell_square (FAST mode table)
    Note: Does NOT modify sightings_sighting.grid_cell_id (isolacja!)
    """
    print("Counting sightings per square grid cell...")

    with connection.cursor() as cursor:
        # Reset counts
        cursor.execute("UPDATE sightings_gridcell_square SET sighting_count = 0;")

        # Count sightings per cell using spatial join (no grid_cell_id modification)
        cursor.execute("""
            UPDATE sightings_gridcell_square g
            SET sighting_count = COALESCE(subq.cnt, 0)
            FROM (
                SELECT gc.grid_id, COUNT(s.id) as cnt
                FROM sightings_gridcell_square gc
                LEFT JOIN sightings_sighting s ON ST_Contains(gc.geometry, s.location)
                WHERE s.status = 'verified' OR s.id IS NULL
                GROUP BY gc.grid_id
            ) subq
            WHERE g.grid_id = subq.grid_id;
        """)

        cursor.execute("""
            SELECT
                SUM(sighting_count),
                COUNT(*) FILTER (WHERE sighting_count > 0)
            FROM sightings_gridcell_square;
        """)
        total_sightings, cells_with_sightings = cursor.fetchone()
        print(f"  Total sightings: {total_sightings or 0} in {cells_with_sightings or 0} cells")


def calculate_risk():
    """Calculate risk scores using percentile ranking.

    Uses: sightings_gridcell_square (FAST mode table)
    """
    print("Calculating FAST risk scores...")

    with connection.cursor() as cursor:
        # Density
        cursor.execute("""
            UPDATE sightings_gridcell_square
            SET sighting_density = sighting_count / NULLIF(ST_Area(ST_Transform(geometry, 2180)) / 1000000.0, 0);
        """)

        # Fixed thresholds based on data distribution (replaces PERCENT_RANK)
        cursor.execute("""
            UPDATE sightings_gridcell_square
            SET
                ensemble_risk = CASE 
                    WHEN sighting_count = 0 THEN 0.05
                    WHEN sighting_count = 1 THEN 0.40
                    WHEN sighting_count = 2 THEN 0.75
                    ELSE 0.95
                END,
                area_rank_score = CASE
                    WHEN sighting_count = 0 THEN 0.03
                    WHEN sighting_count = 1 THEN 0.25
                    WHEN sighting_count = 2 THEN 0.50
                    ELSE 0.70
                END,
                gwr_score = CASE
                    WHEN sighting_count = 0 THEN 0.02
                    WHEN sighting_count = 1 THEN 0.20
                    WHEN sighting_count = 2 THEN 0.45
                    ELSE 0.65
                END;
        """)

        # Confidence
        cursor.execute("""
            UPDATE sightings_gridcell_square SET confidence = CASE
                WHEN sighting_count = 0 THEN 0.2
                WHEN sighting_count < 3 THEN 0.4
                WHEN sighting_count < 6 THEN 0.6
                ELSE 0.8 END;
        """)

        # Update timestamp
        cursor.execute("UPDATE sightings_gridcell_square SET updated_at = NOW();")

        cursor.execute("SELECT COUNT(*) FILTER (WHERE ensemble_risk >= 0.7) FROM sightings_gridcell_square;")
        critical = cursor.fetchone()[0]
        print(f"  Critical cells (risk >= 0.7): {critical}")


def main():
    print("=" * 50)
    print("SETUP SQUARE GRID - Dziki na Białołęce")
    print("Target table: sightings_gridcell_square (FAST mode)")
    print("=" * 50)

    create_grid()
    assign_sightings()
    calculate_risk()

    # Final stats
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*), SUM(sighting_count), MAX(ensemble_risk)
            FROM sightings_gridcell_square
        """)
        total, sightings, max_risk = cursor.fetchone()
        print(f"\nFinal stats:")
        print(f"  Total cells: {total}")
        print(f"  Total sightings: {sightings or 0}")
        print(f"  Max risk: {max_risk:.3f}" if max_risk else "  Max risk: N/A")

    print("=" * 50)
    print("DONE! FAST mode ready.")
    print("=" * 50)


if __name__ == '__main__':
    main()
