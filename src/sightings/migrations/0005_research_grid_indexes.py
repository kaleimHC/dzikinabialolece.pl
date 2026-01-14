from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sightings", "0004_osm_models"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS idx_research_grid_ensemble
            ON research_grid_500m(ensemble_risk);

            CREATE INDEX IF NOT EXISTS idx_research_grid_district
            ON research_grid_500m(district);

            CREATE INDEX IF NOT EXISTS idx_research_grid_regime
            ON research_grid_500m(regime)
            WHERE regime IS NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_voronoi_ensemble
            ON sightings_gridcell_voronoi(ensemble_risk);

            CREATE INDEX IF NOT EXISTS idx_square_ensemble
            ON sightings_gridcell_square(ensemble_risk);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_research_grid_ensemble;
            DROP INDEX IF EXISTS idx_research_grid_district;
            DROP INDEX IF EXISTS idx_research_grid_regime;
            DROP INDEX IF EXISTS idx_voronoi_ensemble;
            DROP INDEX IF EXISTS idx_square_ensemble;
            """,
        ),
    ]
