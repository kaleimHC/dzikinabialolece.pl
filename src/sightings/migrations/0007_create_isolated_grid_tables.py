"""
Migration: Create isolated grid tables for FAST and PUB modes.

This ensures grid tables persist across Docker resets.
Tables:
- sightings_gridcell_square: 100x100m regular grid (FAST mode)
- sightings_gridcell_voronoi: Voronoi tessellation (PUB mode)
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sightings", "0006_add_eta_notebooklm_fields"),
    ]

    operations = [
        # Tabela SQUARE (FAST mode)
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS sightings_gridcell_square (
                id SERIAL PRIMARY KEY,
                grid_id VARCHAR(50) UNIQUE NOT NULL,
                geometry geometry(Geometry, 4326) NOT NULL,
                centroid geometry(Point, 4326),
                district VARCHAR(100),
                sighting_count INTEGER DEFAULT 0,
                sighting_density DOUBLE PRECISION DEFAULT 0,
                ensemble_risk DOUBLE PRECISION DEFAULT 0.05,
                eta_score DOUBLE PRECISION DEFAULT 0,
                gwr_score DOUBLE PRECISION DEFAULT 0,
                confidence DOUBLE PRECISION DEFAULT 0.2,
                building_density DOUBLE PRECISION DEFAULT 0,
                distance_to_forest DOUBLE PRECISION DEFAULT 0,
                distance_to_water DOUBLE PRECISION DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_square_geometry ON sightings_gridcell_square USING GIST(geometry);
            CREATE INDEX IF NOT EXISTS idx_square_grid_id ON sightings_gridcell_square(grid_id);
            """,
            reverse_sql="DROP TABLE IF EXISTS sightings_gridcell_square CASCADE;",
        ),
        # Tabela VORONOI (PUB mode)
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS sightings_gridcell_voronoi (
                id SERIAL PRIMARY KEY,
                grid_id VARCHAR(50) UNIQUE NOT NULL,
                geometry geometry(Geometry, 4326) NOT NULL,
                centroid geometry(Point, 4326),
                district VARCHAR(100),
                sighting_count INTEGER DEFAULT 0,
                sighting_density DOUBLE PRECISION DEFAULT 0,
                ensemble_risk DOUBLE PRECISION DEFAULT 0.05,
                eta_score DOUBLE PRECISION DEFAULT 0,
                gwr_score DOUBLE PRECISION DEFAULT 0,
                confidence DOUBLE PRECISION DEFAULT 0.2,
                building_density DOUBLE PRECISION DEFAULT 0,
                distance_to_forest DOUBLE PRECISION DEFAULT 0,
                distance_to_water DOUBLE PRECISION DEFAULT 0,
                proximity_weight DOUBLE PRECISION DEFAULT 1.0,
                eta_contribution DOUBLE PRECISION DEFAULT 0,
                area_proportion DOUBLE PRECISION DEFAULT 0,
                eta_local DOUBLE PRECISION DEFAULT 0,
                eta_weighted DOUBLE PRECISION DEFAULT 0,
                road_density DOUBLE PRECISION DEFAULT 0,
                gwr_risk DOUBLE PRECISION DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_voronoi_geometry ON sightings_gridcell_voronoi USING GIST(geometry);
            CREATE INDEX IF NOT EXISTS idx_voronoi_grid_id ON sightings_gridcell_voronoi(grid_id);
            """,
            reverse_sql="DROP TABLE IF EXISTS sightings_gridcell_voronoi CASCADE;",
        ),
    ]
