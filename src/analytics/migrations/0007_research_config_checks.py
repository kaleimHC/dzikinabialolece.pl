"""
DB-level defense-in-depth CHECK constraints for ResearchConfig.

Mirrors the model TextChoices + validators + clean() invariants as Postgres
CHECK constraints, so non-button configs cannot be persisted via any ORM
bypass (.update(), bulk_create, admin, raw SQL, a future serializer that
forgets full_clean). Verified against live data: 0 violations, exactly 1
active config. Also repairs the one persisted row that carried the invalid
predictor token 'meadows' (canonical: 'meadow').
"""

from django.db import migrations, models
from django.db.models import Q, F


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0006_alter_researchconfig_y_formula"),
    ]

    operations = [
        # Data repair: RES-12 preset persisted the invalid predictor 'meadows'
        # (plural); the canonical token is 'meadow'. Fix before the new clean()
        # validation and the UI rely on it.
        migrations.RunSQL(
            sql=(
                "UPDATE analytics_researchconfig "
                "SET active_predictors = (active_predictors - 'meadows') || '[\"meadow\"]'::jsonb "
                "WHERE active_predictors @> '[\"meadows\"]'::jsonb;"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(geometry_type__in=["voronoi", "grid_500"]),
                name="rc_geometry_type_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(population_method__in=["spatial_join", "points", "centroid"]),
                name="rc_population_method_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(y_formula__in=["log_intensity", "count_pop", "inv_pop", "log_pop", "log_count", "binary"]),
                name="rc_y_formula_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(w_method__in=["knn_aic", "contiguity", "tessw"]),
                name="rc_w_method_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(model_type__in=["auto", "sar", "sem", "sdm", "probit", "logit"]),
                name="rc_model_type_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(regime_type__in=["none", "trinary"]),
                name="rc_regime_type_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(k_range_min__gte=1),
                name="rc_k_range_min_gte_1",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(k_range_max__gt=F("k_range_min")),
                name="rc_k_range_max_gt_min",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(alpha__gte=0.001) & Q(alpha__lte=0.5),
                name="rc_alpha_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(vif_threshold__gte=1.0) & Q(vif_threshold__lte=100.0),
                name="rc_vif_threshold_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(regime_threshold__gte=0.0) & Q(regime_threshold__lte=1.0),
                name="rc_regime_threshold_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(regime_threshold_urban__gte=0.0) & Q(regime_threshold_urban__lte=1.0),
                name="rc_regime_threshold_urban_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.CheckConstraint(
                check=Q(date_from__isnull=True) | Q(date_to__isnull=True) | Q(date_from__lte=F("date_to")),
                name="rc_date_from_lte_date_to",
            ),
        ),
        migrations.AddConstraint(
            model_name="researchconfig",
            constraint=models.UniqueConstraint(
                fields=["is_active"],
                condition=Q(is_active=True),
                name="rc_single_active_config",
            ),
        ),
    ]
