# Generated manually - Partial indexes for Bayesian results (MASTER_SPEC v2.3 I.2.2)

from django.db import migrations


class Migration(migrations.Migration):
    """
    Add partial indexes for Bayesian results as specified in MASTER_SPEC v2.3.

    These indexes optimize queries for:
    - High-risk alerts (prob_above_threshold > 0.7)
    - Convergence issues (r_hat > 1.01)
    """

    dependencies = [
        ("analytics", "0003_parameterconfiguration"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Partial index for high-risk cells (alerting)
            -- MASTER_SPEC I.2.2: idx_bayes_high_risk
            CREATE INDEX IF NOT EXISTS idx_bayes_high_risk
            ON analytics_bayesian_result(prob_above_threshold)
            WHERE prob_above_threshold > 0.7;

            -- Partial index for convergence issues (diagnostics)
            -- MASTER_SPEC I.2.2: idx_bayes_bad_convergence
            CREATE INDEX IF NOT EXISTS idx_bayes_bad_convergence
            ON analytics_bayesian_result(r_hat)
            WHERE r_hat > 1.01;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_bayes_high_risk;
            DROP INDEX IF EXISTS idx_bayes_bad_convergence;
            """,
        ),
    ]
