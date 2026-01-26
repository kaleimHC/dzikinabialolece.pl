"""
Migration: Create research grid table for spatialWarsaw research mode.

Table: sightings_gridcell_research
This is a THIRD independent grid table for research/development purposes.

Tables isolation:
- sightings_gridcell_square: 100x100m regular grid (FAST mode)
- sightings_gridcell_voronoi: Voronoi tessellation (PUB mode)
- sightings_gridcell_research: Research experiments (RESEARCH mode) [NEW]
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('sightings', '0009_remove_hallucination_columns'),
    ]

    operations = [
        # Tabela RESEARCH (spatialWarsaw research mode)
        migrations.RunSQL(
            sql='''
            CREATE TABLE IF NOT EXISTS sightings_gridcell_research (
                -- Base identifiers
                id SERIAL PRIMARY KEY,
                grid_id VARCHAR(50) UNIQUE NOT NULL,
                geometry geometry(Geometry, 4326) NOT NULL,
                centroid geometry(Point, 4326),

                -- Sighting data
                sighting_id INTEGER,  -- Link to source sighting (for Voronoi 1:1)
                sighting_count INTEGER DEFAULT 0,

                -- Population (from GUS 500m grid)
                population DOUBLE PRECISION DEFAULT 0,

                -- Y variables (different formulas for spatial regression)
                y_inv_pop DOUBLE PRECISION,      -- 1 / population (inverse)
                y_log_pop DOUBLE PRECISION,      -- log(population + 1)
                y_count_pop DOUBLE PRECISION,    -- sighting_count / population
                y_binary SMALLINT DEFAULT 0,     -- 0/1 for logistic

                -- Risk scores from models
                model_fitted DOUBLE PRECISION,   -- Raw model fitted value
                spatial_risk DOUBLE PRECISION DEFAULT 0,  -- Normalized spatial risk [0,1]
                ensemble_risk DOUBLE PRECISION DEFAULT 0.05, -- Final ensemble risk

                -- OSM environmental features
                forest_cover DOUBLE PRECISION DEFAULT 0,
                building_density DOUBLE PRECISION DEFAULT 0,
                road_density DOUBLE PRECISION DEFAULT 0,
                distance_to_water DOUBLE PRECISION DEFAULT 0,
                distance_to_forest DOUBLE PRECISION DEFAULT 0,

                -- Diagnostics
                eta_score DOUBLE PRECISION DEFAULT 0,
                confidence DOUBLE PRECISION DEFAULT 0.5,
                area_proportion DOUBLE PRECISION DEFAULT 0,

                -- Metadata
                run_id VARCHAR(50),  -- Pipeline run identifier
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );

            -- Spatial index on geometry
            CREATE INDEX IF NOT EXISTS idx_research_geometry
                ON sightings_gridcell_research USING GIST(geometry);

            -- B-tree index on grid_id for lookups
            CREATE INDEX IF NOT EXISTS idx_research_grid_id
                ON sightings_gridcell_research(grid_id);

            -- Index on run_id for filtering by pipeline run
            CREATE INDEX IF NOT EXISTS idx_research_run_id
                ON sightings_gridcell_research(run_id);

            -- Partial index for high-risk cells (alerts)
            CREATE INDEX IF NOT EXISTS idx_research_high_risk
                ON sightings_gridcell_research(ensemble_risk)
                WHERE ensemble_risk > 0.7;
            ''',
            reverse_sql='DROP TABLE IF EXISTS sightings_gridcell_research CASCADE;'
        ),
    ]
