"""
Django management command to check and initialize grid tables.

Usage:
    docker exec dziki-api python manage.py init_grids
    docker exec dziki-api python manage.py init_grids --generate-square
    docker exec dziki-api python manage.py init_grids --generate-all
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Check and initialize grid tables for FAST and PUB modes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--generate-square",
            action="store_true",
            help="Generate square grid if empty",
        )
        parser.add_argument(
            "--generate-all",
            action="store_true",
            help="Generate both grids if empty",
        )

    def handle(self, *args, **options):
        self.stdout.write("=== GRID INITIALIZATION CHECK ===\n")

        # Check tables exist
        tables = self._check_tables()
        self.stdout.write(f"Tables found: {tables}")

        missing = []
        if "sightings_gridcell_square" not in tables:
            missing.append("sightings_gridcell_square")
        if "sightings_gridcell_voronoi" not in tables:
            missing.append("sightings_gridcell_voronoi")

        if missing:
            self.stdout.write(self.style.ERROR(f"\nMISSING TABLES: {missing}"))
            self.stdout.write("Run: python manage.py migrate")
            return

        # Check data counts
        counts = self._count_grids()
        self.stdout.write("\nGrid counts:")
        self.stdout.write(f"  - square:  {counts['square']}")
        self.stdout.write(f"  - voronoi: {counts['voronoi']}")

        # Generate if requested
        if options["generate_square"] or options["generate_all"]:
            if counts["square"] == 0:
                self.stdout.write("\nGenerating square grid...")
                self._generate_square_grid()
                counts = self._count_grids()
                self.stdout.write(
                    self.style.SUCCESS(f"Created {counts['square']} square cells")
                )

        # Status
        if counts["square"] == 0:
            self.stdout.write(self.style.WARNING("\nSquare grid is EMPTY!"))
            self.stdout.write("  Run: python manage.py init_grids --generate-square")
            self.stdout.write("  Or:  POST /api/analytics/recalculate/?mode=fast")

        if counts["voronoi"] == 0:
            self.stdout.write(self.style.WARNING("\nVoronoi grid is EMPTY!"))
            self.stdout.write("  Run: Rscript r_scripts/01_generate_voronoi.R")
            self.stdout.write("  Or:  POST /api/analytics/recalculate/?mode=full")

        if counts["square"] > 0 and counts["voronoi"] > 0:
            self.stdout.write(self.style.SUCCESS("\nAll grids initialized!"))

    def _check_tables(self):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('sightings_gridcell_square', 'sightings_gridcell_voronoi')
            """)
            return [row[0] for row in cursor.fetchall()]

    def _count_grids(self):
        results = {"square": 0, "voronoi": 0}
        with connection.cursor() as cursor:
            try:
                cursor.execute("SELECT COUNT(*) FROM sightings_gridcell_square")
                results["square"] = cursor.fetchone()[0]
            except:
                pass
            try:
                cursor.execute("SELECT COUNT(*) FROM sightings_gridcell_voronoi")
                results["voronoi"] = cursor.fetchone()[0]
            except:
                pass
        return results

    def _generate_square_grid(self):
        """Generate 100x100m square grid within Bialoleka."""
        with connection.cursor() as cursor:
            # Clear existing
            cursor.execute("TRUNCATE TABLE sightings_gridcell_square RESTART IDENTITY")

            # Generate grid
            cursor.execute("""
                WITH bialoleka AS (
                    SELECT geom FROM boundaries WHERE name = 'bialoleka'
                ),
                bounds AS (
                    SELECT
                        floor((ST_XMin(ST_Extent(geom)) - 0.002) / 0.001) * 0.001 AS x_min,
                        floor((ST_YMin(ST_Extent(geom)) - 0.002) / 0.001) * 0.001 AS y_min,
                        ceil( (ST_XMax(ST_Extent(geom)) + 0.002) / 0.001) * 0.001 AS x_max,
                        ceil( (ST_YMax(ST_Extent(geom)) + 0.002) / 0.001) * 0.001 AS y_max
                    FROM boundaries WHERE name = 'bialoleka'
                ),
                raw_grid AS (
                    SELECT
                        ROW_NUMBER() OVER () as id,
                        ST_SetSRID(ST_MakeEnvelope(x, y, x + 0.001, y + 0.001, 4326), 4326) as geom
                    FROM bounds,
                         generate_series(x_min::numeric, x_max::numeric, 0.001::numeric) x,
                         generate_series(y_min::numeric, y_max::numeric, 0.001::numeric) y
                ),
                grid_in_bialoleka AS (
                    SELECT g.id, ST_Intersection(g.geom, b.geom) as geom
                    FROM raw_grid g, bialoleka b
                    WHERE ST_Intersects(g.geom, b.geom)
                )
                INSERT INTO sightings_gridcell_square (grid_id, geometry, sighting_count, district, centroid)
                SELECT
                    'GRID-' || id as grid_id,
                    geom as geometry,
                    0 as sighting_count,
                    'Bialoleka' as district,
                    ST_Centroid(geom) as centroid
                FROM grid_in_bialoleka
                WHERE NOT ST_IsEmpty(geom) AND ST_Area(geom::geography) > 50;
            """)

            # Count sightings
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

            # Calculate risk
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
                    END,
                    confidence = CASE
                        WHEN sighting_count = 0 THEN 0.2
                        WHEN sighting_count < 3 THEN 0.4
                        WHEN sighting_count < 6 THEN 0.6
                        ELSE 0.8
                    END,
                    updated_at = NOW();
            """)
