"""
Migration: Rename eta_score to area_rank_score.

The name "eta_score" was misleading - it suggested ETA entropy from spatialWarsaw,
but the actual calculation is: 1 - percentile_rank(area_proportion).
New name "area_rank_score" correctly describes the calculation.

Tables affected:
- sightings_gridcell_voronoi
- sightings_gridcell_square
- research_grid_500m
- research_grid_250m
- sightings_gridcell_research
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sightings", "0011_research_grids"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- ================================================================
            -- Rename eta_score → area_rank_score in all grid tables
            -- ================================================================

            -- 1. sightings_gridcell_voronoi (PUB mode)
            ALTER TABLE sightings_gridcell_voronoi
            RENAME COLUMN eta_score TO area_rank_score;

            -- 2. sightings_gridcell_square (FAST mode)
            ALTER TABLE sightings_gridcell_square
            RENAME COLUMN eta_score TO area_rank_score;

            -- 3. research_grid_500m
            ALTER TABLE research_grid_500m
            RENAME COLUMN eta_score TO area_rank_score;

            -- 4. research_grid_250m
            ALTER TABLE research_grid_250m
            RENAME COLUMN eta_score TO area_rank_score;

            -- 5. sightings_gridcell_research
            ALTER TABLE sightings_gridcell_research
            RENAME COLUMN eta_score TO area_rank_score;

            -- Add comment explaining the column
            COMMENT ON COLUMN sightings_gridcell_voronoi.area_rank_score IS
                'Area-based rank score: 1 - percentile_rank(area_proportion). Smaller tiles = higher score.';
            COMMENT ON COLUMN sightings_gridcell_square.area_rank_score IS
                'Area-based rank score for FAST mode heuristic.';
            COMMENT ON COLUMN research_grid_500m.area_rank_score IS
                'Area-based rank score: 1 - percentile_rank(area_proportion).';
            COMMENT ON COLUMN research_grid_250m.area_rank_score IS
                'Area-based rank score: 1 - percentile_rank(area_proportion).';
            COMMENT ON COLUMN sightings_gridcell_research.area_rank_score IS
                'Area-based rank score: 1 - percentile_rank(area_proportion).';
            """,
            reverse_sql="""
            -- Reverse: area_rank_score → eta_score
            ALTER TABLE sightings_gridcell_voronoi
            RENAME COLUMN area_rank_score TO eta_score;

            ALTER TABLE sightings_gridcell_square
            RENAME COLUMN area_rank_score TO eta_score;

            ALTER TABLE research_grid_500m
            RENAME COLUMN area_rank_score TO eta_score;

            ALTER TABLE research_grid_250m
            RENAME COLUMN area_rank_score TO eta_score;

            ALTER TABLE sightings_gridcell_research
            RENAME COLUMN area_rank_score TO eta_score;
            """,
        ),
    ]
