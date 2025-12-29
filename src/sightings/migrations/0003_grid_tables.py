"""
Migration: Grid tables for FAST, PUB and RESEARCH modes.

Four isolated tables, each in its final column form:
- sightings_gridcell_square:   100×100m regular grid (FAST mode)
- sightings_gridcell_voronoi:  Voronoi tessellation  (PUB mode)
- sightings_gridcell_research: Research experiments  (RESEARCH mode)
- research_grid_500m:          ~500m regular grid    (RESEARCH spatial regression)
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sightings", "0002_gridcell_complete"),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # SQUARE  (FAST mode - 100×100m regular grid, ~9 875 cells)          #
        # ------------------------------------------------------------------ #
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS sightings_gridcell_square (
                id               SERIAL PRIMARY KEY,
                grid_id          VARCHAR(50) UNIQUE NOT NULL,
                geometry         geometry(Geometry, 4326) NOT NULL,
                centroid         geometry(Point, 4326),
                district         VARCHAR(100),
                sighting_count   INTEGER          DEFAULT 0,
                sighting_density DOUBLE PRECISION DEFAULT 0,
                ensemble_risk    DOUBLE PRECISION DEFAULT 0.05,
                area_rank_score  DOUBLE PRECISION DEFAULT 0,
                gwr_score        DOUBLE PRECISION DEFAULT 0,
                confidence       DOUBLE PRECISION DEFAULT 0.2,
                building_density    DOUBLE PRECISION DEFAULT 0,
                distance_to_forest  DOUBLE PRECISION DEFAULT 0,
                distance_to_water   DOUBLE PRECISION DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_square_geometry
                ON sightings_gridcell_square USING GIST(geometry);
            CREATE INDEX IF NOT EXISTS idx_square_grid_id
                ON sightings_gridcell_square(grid_id);
            """,
            reverse_sql="DROP TABLE IF EXISTS sightings_gridcell_square CASCADE;",
        ),
        # ------------------------------------------------------------------ #
        # VORONOI  (PUB mode - Voronoi tessellation, ~100-500 cells)         #
        # ------------------------------------------------------------------ #
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS sightings_gridcell_voronoi (
                id               SERIAL PRIMARY KEY,
                grid_id          VARCHAR(50) UNIQUE NOT NULL,
                geometry         geometry(Geometry, 4326) NOT NULL,
                centroid         geometry(Point, 4326),
                district         VARCHAR(100),
                sighting_count   INTEGER          DEFAULT 0,
                spatial_risk     DOUBLE PRECISION DEFAULT 0,
                model_fitted     DOUBLE PRECISION DEFAULT 0,
                ensemble_risk    DOUBLE PRECISION DEFAULT 0.05,
                area_rank_score  DOUBLE PRECISION DEFAULT 0,
                gwr_score        DOUBLE PRECISION DEFAULT 0,
                confidence       DOUBLE PRECISION DEFAULT 0.2,
                building_density    DOUBLE PRECISION DEFAULT 0,
                distance_to_forest  DOUBLE PRECISION DEFAULT 0,
                distance_to_water   DOUBLE PRECISION DEFAULT 0,
                eta_contribution    DOUBLE PRECISION DEFAULT 0,
                area_proportion     DOUBLE PRECISION DEFAULT 0,
                eta_local           DOUBLE PRECISION DEFAULT 0,
                eta_weighted        DOUBLE PRECISION DEFAULT 0,
                road_density        DOUBLE PRECISION DEFAULT 0,
                gwr_risk            DOUBLE PRECISION DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_voronoi_geometry
                ON sightings_gridcell_voronoi USING GIST(geometry);
            CREATE INDEX IF NOT EXISTS idx_voronoi_grid_id
                ON sightings_gridcell_voronoi(grid_id);
            """,
            reverse_sql="DROP TABLE IF EXISTS sightings_gridcell_voronoi CASCADE;",
        ),
        # ------------------------------------------------------------------ #
        # RESEARCH  (research Voronoi experiments, ~500 cells)               #
        # ------------------------------------------------------------------ #
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS sightings_gridcell_research (
                id              SERIAL PRIMARY KEY,
                grid_id         VARCHAR(50) UNIQUE NOT NULL,
                geometry        geometry(Geometry, 4326) NOT NULL,
                centroid        geometry(Point, 4326),
                sighting_id     INTEGER,
                sighting_count  INTEGER          DEFAULT 0,
                population      DOUBLE PRECISION DEFAULT 0,
                regime          VARCHAR(10)      DEFAULT 'mixed',
                y_inv_pop       DOUBLE PRECISION,
                y_log_pop       DOUBLE PRECISION,
                y_count_pop     DOUBLE PRECISION,
                y_binary        SMALLINT         DEFAULT 0,
                model_fitted    DOUBLE PRECISION,
                spatial_risk    DOUBLE PRECISION DEFAULT 0,
                ensemble_risk   DOUBLE PRECISION DEFAULT 0.05,
                forest_cover    DOUBLE PRECISION DEFAULT 0,
                building_density   DOUBLE PRECISION DEFAULT 0,
                road_density       DOUBLE PRECISION DEFAULT 0,
                distance_to_water  DOUBLE PRECISION DEFAULT 0,
                distance_to_forest DOUBLE PRECISION DEFAULT 0,
                confidence      DOUBLE PRECISION DEFAULT 0.5,
                area_proportion DOUBLE PRECISION DEFAULT 0,
                run_id          VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_research_geometry
                ON sightings_gridcell_research USING GIST(geometry);
            CREATE INDEX IF NOT EXISTS idx_research_grid_id
                ON sightings_gridcell_research(grid_id);
            CREATE INDEX IF NOT EXISTS idx_research_run_id
                ON sightings_gridcell_research(run_id);
            CREATE INDEX IF NOT EXISTS idx_research_high_risk
                ON sightings_gridcell_research(ensemble_risk)
                WHERE ensemble_risk > 0.7;
            """,
            reverse_sql="DROP TABLE IF EXISTS sightings_gridcell_research CASCADE;",
        ),
        # ------------------------------------------------------------------ #
        # RESEARCH_GRID_500M  (~500m regular grid, ~80 cells for SAR/SEM)   #
        # ------------------------------------------------------------------ #
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS research_grid_500m (
                id              SERIAL PRIMARY KEY,
                grid_id         VARCHAR(50) UNIQUE NOT NULL,
                geometry        geometry(Polygon, 4326) NOT NULL,
                centroid        geometry(Point, 4326),
                sighting_id     INTEGER,
                sighting_count  INTEGER          DEFAULT 0,
                population      DOUBLE PRECISION DEFAULT 0,
                regime          VARCHAR(10)      DEFAULT 'mixed',
                regime_probability DOUBLE PRECISION,
                y_inv_pop       DOUBLE PRECISION,
                y_log_pop       DOUBLE PRECISION,
                y_count_pop     DOUBLE PRECISION,
                y_binary        SMALLINT         DEFAULT 0,
                model_fitted    DOUBLE PRECISION,
                spatial_risk    DOUBLE PRECISION DEFAULT 0,
                spatial_risk_pop DOUBLE PRECISION,
                ensemble_risk   DOUBLE PRECISION DEFAULT 0.05,
                forest_cover    DOUBLE PRECISION DEFAULT 0,
                building_density   DOUBLE PRECISION DEFAULT 0,
                road_density       DOUBLE PRECISION DEFAULT 0,
                distance_to_water  DOUBLE PRECISION DEFAULT 0,
                distance_to_forest DOUBLE PRECISION DEFAULT 0,
                park_cover         DOUBLE PRECISION DEFAULT 0,
                meadow_cover       DOUBLE PRECISION DEFAULT 0,
                farmland_cover     DOUBLE PRECISION DEFAULT 0,
                allotment_cover    DOUBLE PRECISION DEFAULT 0,
                scrub_cover        DOUBLE PRECISION DEFAULT 0,
                railway_density    DOUBLE PRECISION DEFAULT 0,
                barrier_resistance DOUBLE PRECISION DEFAULT 0,
                hedge_corridor_km  DOUBLE PRECISION DEFAULT 0,
                hedge_factor       DOUBLE PRECISION DEFAULT 0,
                eta_contribution   DOUBLE PRECISION DEFAULT 0,
                gwr_score          DOUBLE PRECISION DEFAULT 0,
                confidence         DOUBLE PRECISION DEFAULT 0.5,
                area_proportion    DOUBLE PRECISION DEFAULT 0,
                proximity_weight   DOUBLE PRECISION DEFAULT 1.0,
                district           VARCHAR(100),
                run_id             UUID,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_grid500_geom
                ON research_grid_500m USING GIST(geometry);
            CREATE INDEX IF NOT EXISTS idx_grid500_grid_id
                ON research_grid_500m(grid_id);
            CREATE INDEX IF NOT EXISTS idx_grid500_run
                ON research_grid_500m(run_id);
            CREATE INDEX IF NOT EXISTS idx_grid500_regime
                ON research_grid_500m(regime);
            """,
            reverse_sql="DROP TABLE IF EXISTS research_grid_500m CASCADE;",
        ),
    ]
