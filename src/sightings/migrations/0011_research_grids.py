"""
Migration: Create research grid tables for 500m and 250m regular grids.

Tables:
- research_grid_500m: Regular grid ~500m cells for research (N~80)
- research_grid_250m: Regular grid ~250m cells for research (N~320)

Also adds regime columns to existing sightings_gridcell_research.

Tables isolation:
- sightings_gridcell_square: 100x100m regular grid (FAST mode) - UNCHANGED
- sightings_gridcell_voronoi: Voronoi tessellation (PUB mode) - UNCHANGED
- sightings_gridcell_research: Voronoi for research (RESEARCH mode) - ADD regime
- research_grid_500m: 500m grid for research (RESEARCH mode) - NEW
- research_grid_250m: 250m grid for research (RESEARCH mode) - NEW
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sightings', '0010_create_research_grid_table'),
    ]

    operations = [
        migrations.RunSQL(
            sql='''
            -- ================================================================
            -- research_grid_500m: Regular grid ~500m cells
            -- Expected: ~80 cells covering Bialoleka
            -- ================================================================
            CREATE TABLE IF NOT EXISTS research_grid_500m (
                -- Base identifiers
                id SERIAL PRIMARY KEY,
                grid_id VARCHAR(50) UNIQUE NOT NULL,
                geometry geometry(Polygon, 4326) NOT NULL,
                centroid geometry(Point, 4326),

                -- Sighting data
                sighting_id INTEGER,
                sighting_count INTEGER DEFAULT 0,

                -- Population (from GUS 500m grid)
                population DOUBLE PRECISION DEFAULT 0,

                -- REGIME (NEW for Binary/ST-SAR models)
                regime VARCHAR(10) DEFAULT 'mixed',  -- 'forest' / 'urban' / 'mixed'
                regime_probability DOUBLE PRECISION,  -- P(forest) for ST-SAR

                -- Y variables (different formulas for spatial regression)
                y_inv_pop DOUBLE PRECISION,
                y_log_pop DOUBLE PRECISION,
                y_count_pop DOUBLE PRECISION,
                y_binary SMALLINT DEFAULT 0,

                -- Risk scores from models
                model_fitted DOUBLE PRECISION,
                spatial_risk DOUBLE PRECISION DEFAULT 0,
                spatial_risk_pop DOUBLE PRECISION,
                ensemble_risk DOUBLE PRECISION DEFAULT 0.05,

                -- OSM environmental features (all from research table)
                forest_cover DOUBLE PRECISION DEFAULT 0,
                building_density DOUBLE PRECISION DEFAULT 0,
                road_density DOUBLE PRECISION DEFAULT 0,
                distance_to_water DOUBLE PRECISION DEFAULT 0,
                distance_to_forest DOUBLE PRECISION DEFAULT 0,
                park_cover DOUBLE PRECISION DEFAULT 0,
                meadow_cover DOUBLE PRECISION DEFAULT 0,
                farmland_cover DOUBLE PRECISION DEFAULT 0,
                allotment_cover DOUBLE PRECISION DEFAULT 0,
                scrub_cover DOUBLE PRECISION DEFAULT 0,
                railway_density DOUBLE PRECISION DEFAULT 0,
                barrier_resistance DOUBLE PRECISION DEFAULT 0,
                hedge_corridor_km DOUBLE PRECISION DEFAULT 0,
                hedge_factor DOUBLE PRECISION DEFAULT 0,

                -- Diagnostics
                eta_score DOUBLE PRECISION DEFAULT 0,
                eta_contribution DOUBLE PRECISION DEFAULT 0,
                gwr_score DOUBLE PRECISION DEFAULT 0,
                rf_score DOUBLE PRECISION,
                confidence DOUBLE PRECISION DEFAULT 0.5,
                area_proportion DOUBLE PRECISION DEFAULT 0,
                sighting_density DOUBLE PRECISION DEFAULT 0,
                proximity_weight DOUBLE PRECISION DEFAULT 1.0,

                -- Metadata
                district VARCHAR(100),
                run_id UUID,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );

            -- Indexes for research_grid_500m
            CREATE INDEX IF NOT EXISTS idx_grid500_geom ON research_grid_500m USING GIST(geometry);
            CREATE INDEX IF NOT EXISTS idx_grid500_grid_id ON research_grid_500m(grid_id);
            CREATE INDEX IF NOT EXISTS idx_grid500_run ON research_grid_500m(run_id);
            CREATE INDEX IF NOT EXISTS idx_grid500_regime ON research_grid_500m(regime);
            CREATE INDEX IF NOT EXISTS idx_grid500_high_risk ON research_grid_500m(ensemble_risk) WHERE ensemble_risk > 0.7;

            -- ================================================================
            -- research_grid_250m: Regular grid ~250m cells
            -- Expected: ~320 cells covering Bialoleka
            -- ================================================================
            CREATE TABLE IF NOT EXISTS research_grid_250m (
                -- Base identifiers
                id SERIAL PRIMARY KEY,
                grid_id VARCHAR(50) UNIQUE NOT NULL,
                geometry geometry(Polygon, 4326) NOT NULL,
                centroid geometry(Point, 4326),

                -- Sighting data
                sighting_id INTEGER,
                sighting_count INTEGER DEFAULT 0,

                -- Population (from GUS 500m grid)
                population DOUBLE PRECISION DEFAULT 0,

                -- REGIME (NEW for Binary/ST-SAR models)
                regime VARCHAR(10) DEFAULT 'mixed',
                regime_probability DOUBLE PRECISION,

                -- Y variables
                y_inv_pop DOUBLE PRECISION,
                y_log_pop DOUBLE PRECISION,
                y_count_pop DOUBLE PRECISION,
                y_binary SMALLINT DEFAULT 0,

                -- Risk scores
                model_fitted DOUBLE PRECISION,
                spatial_risk DOUBLE PRECISION DEFAULT 0,
                spatial_risk_pop DOUBLE PRECISION,
                ensemble_risk DOUBLE PRECISION DEFAULT 0.05,

                -- OSM environmental features
                forest_cover DOUBLE PRECISION DEFAULT 0,
                building_density DOUBLE PRECISION DEFAULT 0,
                road_density DOUBLE PRECISION DEFAULT 0,
                distance_to_water DOUBLE PRECISION DEFAULT 0,
                distance_to_forest DOUBLE PRECISION DEFAULT 0,
                park_cover DOUBLE PRECISION DEFAULT 0,
                meadow_cover DOUBLE PRECISION DEFAULT 0,
                farmland_cover DOUBLE PRECISION DEFAULT 0,
                allotment_cover DOUBLE PRECISION DEFAULT 0,
                scrub_cover DOUBLE PRECISION DEFAULT 0,
                railway_density DOUBLE PRECISION DEFAULT 0,
                barrier_resistance DOUBLE PRECISION DEFAULT 0,
                hedge_corridor_km DOUBLE PRECISION DEFAULT 0,
                hedge_factor DOUBLE PRECISION DEFAULT 0,

                -- Diagnostics
                eta_score DOUBLE PRECISION DEFAULT 0,
                eta_contribution DOUBLE PRECISION DEFAULT 0,
                gwr_score DOUBLE PRECISION DEFAULT 0,
                rf_score DOUBLE PRECISION,
                confidence DOUBLE PRECISION DEFAULT 0.5,
                area_proportion DOUBLE PRECISION DEFAULT 0,
                sighting_density DOUBLE PRECISION DEFAULT 0,
                proximity_weight DOUBLE PRECISION DEFAULT 1.0,

                -- Metadata
                district VARCHAR(100),
                run_id UUID,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );

            -- Indexes for research_grid_250m
            CREATE INDEX IF NOT EXISTS idx_grid250_geom ON research_grid_250m USING GIST(geometry);
            CREATE INDEX IF NOT EXISTS idx_grid250_grid_id ON research_grid_250m(grid_id);
            CREATE INDEX IF NOT EXISTS idx_grid250_run ON research_grid_250m(run_id);
            CREATE INDEX IF NOT EXISTS idx_grid250_regime ON research_grid_250m(regime);
            CREATE INDEX IF NOT EXISTS idx_grid250_high_risk ON research_grid_250m(ensemble_risk) WHERE ensemble_risk > 0.7;

            -- ================================================================
            -- Add regime columns to existing sightings_gridcell_research
            -- ================================================================
            ALTER TABLE sightings_gridcell_research
            ADD COLUMN IF NOT EXISTS regime VARCHAR(10) DEFAULT 'mixed';

            ALTER TABLE sightings_gridcell_research
            ADD COLUMN IF NOT EXISTS regime_probability DOUBLE PRECISION;

            CREATE INDEX IF NOT EXISTS idx_research_regime
            ON sightings_gridcell_research(regime);
            ''',
            reverse_sql='''
            DROP TABLE IF EXISTS research_grid_500m CASCADE;
            DROP TABLE IF EXISTS research_grid_250m CASCADE;
            ALTER TABLE sightings_gridcell_research DROP COLUMN IF EXISTS regime;
            ALTER TABLE sightings_gridcell_research DROP COLUMN IF EXISTS regime_probability;
            DROP INDEX IF EXISTS idx_research_regime;
            '''
        ),
    ]
