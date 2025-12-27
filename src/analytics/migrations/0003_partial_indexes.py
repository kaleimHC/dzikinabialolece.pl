"""
Migration: Partial indexes for pipeline execution history.

Partial indexes optimize common dashboard queries:
- Completed pipeline runs (most frequent query)
- Failed runs (alerting / diagnostics)
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0002_parameterconfiguration"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS idx_analytics_run_completed
            ON analytics_analyticsrun(started_at DESC)
            WHERE status = 'completed';

            CREATE INDEX IF NOT EXISTS idx_analytics_run_failed
            ON analytics_analyticsrun(started_at DESC)
            WHERE status = 'failed';
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_analytics_run_completed;
            DROP INDEX IF EXISTS idx_analytics_run_failed;
            """,
        ),
    ]
