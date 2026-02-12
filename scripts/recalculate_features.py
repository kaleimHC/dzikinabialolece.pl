#!/usr/bin/env python3
"""
RECALCULATE FEATURES - Przelicz cechy środowiskowe po naprawie OSM

Przelicza dla każdej komórki Voronoi:
1. forest_cover - % pokrycia lasem
2. building_density - % pokrycia zabudową
3. road_density - km dróg na km²
4. distance_to_water - odległość do wody
6. hedge_corridor_km - km żywopłotów
7. barrier_resistance - opór barier
8. NOWE: allotment_cover - % pokrycia ROD
9. NOWE: meadow_cover - % pokrycia łąkami
10. NOWE: park_cover - % pokrycia parkami

Autor: Claude Code
Data: 2024-01-11
"""

import psycopg2
import sys
import os

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "dziki_db"),
    "user": os.getenv("DB_USER", "dziki"),
    "password": os.getenv("DB_PASSWORD", "dziki_dev_password"),
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432))
}


def main():
    print("=" * 70)
    print("RECALCULATE FEATURES - Przeliczanie cech środowiskowych")
    print("=" * 70)

    # Połączenie z bazą
    print("\n[1] Łączenie z bazą danych...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("  Połączono!")
    except Exception as e:
        print(f"  BŁĄD: {e}")
        sys.exit(1)

    # Dodaj nowe kolumny jeśli nie istnieją
    print("\n[2] Dodawanie nowych kolumn...")

    new_columns = [
        ("allotment_cover", "FLOAT DEFAULT 0"),
        ("meadow_cover", "FLOAT DEFAULT 0"),
        ("park_cover", "FLOAT DEFAULT 0"),
        ("scrub_cover", "FLOAT DEFAULT 0"),
        ("farmland_cover", "FLOAT DEFAULT 0"),
    ]

    for col_name, col_type in new_columns:
        try:
            cur.execute(f"""
                ALTER TABLE sightings_gridcell_voronoi
                ADD COLUMN IF NOT EXISTS {col_name} {col_type};
            """)
            print(f"  + {col_name}")
        except Exception as e:
            print(f"  ! {col_name}: {e}")

    conn.commit()

    # Przelicz forest_cover
    print("\n[3] Przeliczanie forest_cover...")
    cur.execute("""
        UPDATE sightings_gridcell_voronoi gc
        SET forest_cover = COALESCE(subq.cover, 0)
        FROM (
            SELECT
                gc2.id,
                SUM(ST_Area(ST_Intersection(gc2.geometry, f.geom)::geography)) /
                    NULLIF(ST_Area(gc2.geometry::geography), 0) as cover
            FROM sightings_gridcell_voronoi gc2
            LEFT JOIN osm_forests f ON ST_Intersects(gc2.geometry, f.geom)
            GROUP BY gc2.id
        ) subq
        WHERE gc.id = subq.id;
    """)
    print(f"  Zaktualizowano {cur.rowcount} komórek")

    # Przelicz building_density
    print("\n[4] Przeliczanie building_density...")
    cur.execute("""
        UPDATE sightings_gridcell_voronoi gc
        SET building_density = COALESCE(subq.density, 0)
        FROM (
            SELECT
                gc2.id,
                SUM(ST_Area(ST_Intersection(gc2.geometry, b.geom)::geography)) /
                    NULLIF(ST_Area(gc2.geometry::geography), 0) as density
            FROM sightings_gridcell_voronoi gc2
            LEFT JOIN osm_buildings b ON ST_Intersects(gc2.geometry, b.geom)
            GROUP BY gc2.id
        ) subq
        WHERE gc.id = subq.id;
    """)
    print(f"  Zaktualizowano {cur.rowcount} komórek")

    # Przelicz road_density (km/km²)
    print("\n[5] Przeliczanie road_density...")
    cur.execute("""
        UPDATE sightings_gridcell_voronoi gc
        SET road_density = COALESCE(subq.density, 0)
        FROM (
            SELECT
                gc2.id,
                SUM(ST_Length(ST_Intersection(gc2.geometry, r.geom)::geography)) / 1000 /
                    NULLIF(ST_Area(gc2.geometry::geography) / 1000000, 0) as density
            FROM sightings_gridcell_voronoi gc2
            LEFT JOIN osm_roads r ON ST_Intersects(gc2.geometry, r.geom)
            GROUP BY gc2.id
        ) subq
        WHERE gc.id = subq.id;
    """)
    print(f"  Zaktualizowano {cur.rowcount} komórek")

    # Przelicz distance_to_water
    print("\n[6] Przeliczanie distance_to_water...")
    cur.execute("""
        UPDATE sightings_gridcell_voronoi gc
        SET distance_to_water = COALESCE(subq.dist, 9999)
        FROM (
            SELECT
                gc2.id,
                MIN(ST_Distance(gc2.centroid::geography, w.geom::geography)) as dist
            FROM sightings_gridcell_voronoi gc2
            CROSS JOIN osm_water w
            GROUP BY gc2.id
        ) subq
        WHERE gc.id = subq.id;
    """)
    print(f"  Zaktualizowano {cur.rowcount} komórek")


    # Przelicz hedge_corridor_km
    print("\n[7] Przeliczanie hedge_corridor_km...")
    cur.execute("""
        UPDATE sightings_gridcell_voronoi gc
        SET hedge_corridor_km = COALESCE(subq.hedge_km, 0)
        FROM (
            SELECT
                gc2.id,
                SUM(ST_Length(ST_Intersection(gc2.geometry, b.geom)::geography)) / 1000 as hedge_km
            FROM sightings_gridcell_voronoi gc2
            LEFT JOIN osm_barriers b ON ST_Intersects(gc2.geometry, b.geom)
                AND b.barrier_type = 'hedge'
            GROUP BY gc2.id
        ) subq
        WHERE gc.id = subq.id;
    """)
    print(f"  Zaktualizowano {cur.rowcount} komórek")

    # Przelicz barrier_resistance
    print("\n[8] Przeliczanie barrier_resistance...")
    cur.execute("""
        UPDATE sightings_gridcell_voronoi gc
        SET barrier_resistance = COALESCE(subq.resistance, 0)
        FROM (
            SELECT
                gc2.id,
                SUM(ST_Length(ST_Intersection(gc2.geometry, b.geom)::geography) * (1 - COALESCE(b.permeability, 0.5))) /
                    NULLIF(ST_Area(gc2.geometry::geography), 0) as resistance
            FROM sightings_gridcell_voronoi gc2
            LEFT JOIN osm_barriers b ON ST_Intersects(gc2.geometry, b.geom)
            GROUP BY gc2.id
        ) subq
        WHERE gc.id = subq.id;
    """)
    print(f"  Zaktualizowano {cur.rowcount} komórek")

    # Przelicz allotment_cover (jeśli tabela istnieje)
    print("\n[9] Przeliczanie allotment_cover...")
    try:
        cur.execute("""
            UPDATE sightings_gridcell_voronoi gc
            SET allotment_cover = COALESCE(subq.cover, 0)
            FROM (
                SELECT
                    gc2.id,
                    SUM(ST_Area(ST_Intersection(gc2.geometry, a.geom)::geography)) /
                        NULLIF(ST_Area(gc2.geometry::geography), 0) as cover
                FROM sightings_gridcell_voronoi gc2
                LEFT JOIN osm_allotments a ON ST_Intersects(gc2.geometry, a.geom)
                GROUP BY gc2.id
            ) subq
            WHERE gc.id = subq.id;
        """)
        print(f"  Zaktualizowano {cur.rowcount} komórek")
    except Exception as e:
        print(f"  Pominięto (tabela nie istnieje): {e}")

    # Przelicz meadow_cover (jeśli tabela istnieje)
    print("\n[11] Przeliczanie meadow_cover...")
    try:
        cur.execute("""
            UPDATE sightings_gridcell_voronoi gc
            SET meadow_cover = COALESCE(subq.cover, 0)
            FROM (
                SELECT
                    gc2.id,
                    SUM(ST_Area(ST_Intersection(gc2.geometry, m.geom)::geography)) /
                        NULLIF(ST_Area(gc2.geometry::geography), 0) as cover
                FROM sightings_gridcell_voronoi gc2
                LEFT JOIN osm_meadow m ON ST_Intersects(gc2.geometry, m.geom)
                GROUP BY gc2.id
            ) subq
            WHERE gc.id = subq.id;
        """)
        print(f"  Zaktualizowano {cur.rowcount} komórek")
    except Exception as e:
        print(f"  Pominięto (tabela nie istnieje): {e}")

    # Przelicz park_cover (jeśli tabela istnieje)
    print("\n[12] Przeliczanie park_cover...")
    try:
        cur.execute("""
            UPDATE sightings_gridcell_voronoi gc
            SET park_cover = COALESCE(subq.cover, 0)
            FROM (
                SELECT
                    gc2.id,
                    SUM(ST_Area(ST_Intersection(gc2.geometry, p.geom)::geography)) /
                        NULLIF(ST_Area(gc2.geometry::geography), 0) as cover
                FROM sightings_gridcell_voronoi gc2
                LEFT JOIN osm_parks p ON ST_Intersects(gc2.geometry, p.geom)
                GROUP BY gc2.id
            ) subq
            WHERE gc.id = subq.id;
        """)
        print(f"  Zaktualizowano {cur.rowcount} komórek")
    except Exception as e:
        print(f"  Pominięto (tabela nie istnieje): {e}")

    # Przelicz scrub_cover
    print("\n[13] Przeliczanie scrub_cover...")
    try:
        cur.execute("""
            UPDATE sightings_gridcell_voronoi gc
            SET scrub_cover = COALESCE(subq.cover, 0)
            FROM (
                SELECT
                    gc2.id,
                    SUM(ST_Area(ST_Intersection(gc2.geometry, s.geom)::geography)) /
                        NULLIF(ST_Area(gc2.geometry::geography), 0) as cover
                FROM sightings_gridcell_voronoi gc2
                LEFT JOIN osm_scrub s ON ST_Intersects(gc2.geometry, s.geom)
                GROUP BY gc2.id
            ) subq
            WHERE gc.id = subq.id;
        """)
        print(f"  Zaktualizowano {cur.rowcount} komórek")
    except Exception as e:
        print(f"  Pominięto (tabela nie istnieje): {e}")

    # Przelicz farmland_cover
    print("\n[14] Przeliczanie farmland_cover...")
    try:
        cur.execute("""
            UPDATE sightings_gridcell_voronoi gc
            SET farmland_cover = COALESCE(subq.cover, 0)
            FROM (
                SELECT
                    gc2.id,
                    SUM(ST_Area(ST_Intersection(gc2.geometry, f.geom)::geography)) /
                        NULLIF(ST_Area(gc2.geometry::geography), 0) as cover
                FROM sightings_gridcell_voronoi gc2
                LEFT JOIN osm_farmland f ON ST_Intersects(gc2.geometry, f.geom)
                GROUP BY gc2.id
            ) subq
            WHERE gc.id = subq.id;
        """)
        print(f"  Zaktualizowano {cur.rowcount} komórek")
    except Exception as e:
        print(f"  Pominięto (tabela nie istnieje): {e}")

    conn.commit()

    # Statystyki końcowe
    print("\n" + "=" * 70)
    print("STATYSTYKI KOŃCOWE")
    print("=" * 70)

    cur.execute("""
        SELECT
            'forest_cover' as feature,
            ROUND(MIN(forest_cover)::numeric, 4) as min,
            ROUND(AVG(forest_cover)::numeric, 4) as avg,
            ROUND(MAX(forest_cover)::numeric, 4) as max
        FROM sightings_gridcell_voronoi
        UNION ALL
        SELECT 'building_density', ROUND(MIN(building_density)::numeric, 4),
            ROUND(AVG(building_density)::numeric, 4), ROUND(MAX(building_density)::numeric, 4)
        FROM sightings_gridcell_voronoi
        UNION ALL
        SELECT 'road_density', ROUND(MIN(road_density)::numeric, 2),
            ROUND(AVG(road_density)::numeric, 2), ROUND(MAX(road_density)::numeric, 2)
        FROM sightings_gridcell_voronoi
        UNION ALL
        SELECT 'distance_to_water', ROUND(MIN(distance_to_water)::numeric, 0),
            ROUND(AVG(distance_to_water)::numeric, 0), ROUND(MAX(distance_to_water)::numeric, 0)
        FROM sightings_gridcell_voronoi
        UNION ALL
        SELECT 'hedge_corridor_km', ROUND(MIN(hedge_corridor_km)::numeric, 3),
            ROUND(AVG(hedge_corridor_km)::numeric, 3), ROUND(MAX(hedge_corridor_km)::numeric, 3)
        FROM sightings_gridcell_voronoi
        UNION ALL
        SELECT 'allotment_cover', ROUND(MIN(allotment_cover)::numeric, 4),
            ROUND(AVG(allotment_cover)::numeric, 4), ROUND(MAX(allotment_cover)::numeric, 4)
        FROM sightings_gridcell_voronoi;
    """)

    print(f"\n{'Feature':<20} {'Min':>10} {'Avg':>10} {'Max':>10}")
    print("-" * 52)
    for row in cur.fetchall():
        print(f"{row[0]:<20} {row[1]:>10} {row[2]:>10} {row[3]:>10}")

    cur.close()
    conn.close()

    print("\n" + "=" * 70)
    print("ZAKOŃCZONO!")
    print("=" * 70)
    print("\nTeraz uruchom R pipeline żeby przeliczyć ensemble:")
    print("  docker-compose run --rm worker-r Rscript /app/r_scripts/05_ensemble_prediction.R")


if __name__ == "__main__":
    main()
