"""
Management command to load research presets as database configurations.

Usage:
    python manage.py load_research_presets

This will:
1. Delete ALL existing ResearchConfig records
2. Create new configs from predefined presets
3. Activate the first (recommended) preset
"""

from django.core.management.base import BaseCommand
from analytics.models_research import ResearchConfig


# Presets definition - mirrors frontend/src/panels/ResearchPanel/presets.js
RESEARCH_PRESETS = {
    # ─────────────────────────────────────────────────────────────
    # GRUPA A: PODSTAWOWE
    # ─────────────────────────────────────────────────────────────
    "RES-01": {
        "name": "Mapa Ryzyka (Podstawowe)",
        "group": "Podstawowe",
        "recommended": True,
        "config": {
            "geometry_type": "grid_500",
            "population_method": "spatial_join",
            "y_formula": "log_count",
            "model_type": "auto",
            "w_method": "knn_aic",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": True,
            "regime_type": "trinary",
            "regime_threshold_urban": 0.15,
            "regime_threshold": 0.3,
            "active_predictors": [
                "forests",
                "buildings",
                "roads",
                "water",
                "barriers",
                "scrub",
            ],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": True,
            "run_lisa": False,
            "run_eta": False,
            "seed": 42,
        },
    },
    "RES-02": {
        "name": "Model SAR (Podstawowe)",
        "group": "Podstawowe",
        "config": {
            "geometry_type": "grid_500",
            "population_method": "spatial_join",
            "y_formula": "log_count",
            "model_type": "sar",
            "w_method": "knn_aic",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": True,
            "regime_type": "trinary",
            "regime_threshold_urban": 0.15,
            "regime_threshold": 0.3,
            "active_predictors": ["forests", "buildings", "roads", "water"],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": True,
            "run_lisa": False,
            "run_eta": False,
            "seed": 42,
        },
    },
    "RES-03": {
        "name": "Model SEM (Podstawowe)",
        "group": "Podstawowe",
        "config": {
            "geometry_type": "grid_500",
            "population_method": "spatial_join",
            "y_formula": "log_count",
            "model_type": "sem",
            "w_method": "knn_aic",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": True,
            "regime_type": "trinary",
            "regime_threshold_urban": 0.15,
            "regime_threshold": 0.3,
            "active_predictors": ["forests", "buildings", "roads", "water"],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": True,
            "run_lisa": False,
            "run_eta": False,
            "seed": 42,
        },
    },
    "RES-06": {
        "name": "Model Durbina SDM (Podstawowe)",
        "group": "Podstawowe",
        "config": {
            "geometry_type": "grid_500",
            "population_method": "spatial_join",
            "y_formula": "log_count",
            "model_type": "sdm",
            "w_method": "knn_aic",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": False,
            "regime_type": "none",
            "regime_threshold": 0.3,
            "active_predictors": ["forests", "buildings", "water"],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": True,
            "run_lisa": False,
            "run_eta": False,
            "seed": 42,
        },
    },
    # ─────────────────────────────────────────────────────────────
    # GRUPA B: ANALIZA ŚRODOWISKOWA
    # ─────────────────────────────────────────────────────────────
    "RES-08": {
        "name": "Wplyw lasow (Srodowiskowe)",
        "group": "Srodowiskowe",
        "config": {
            "geometry_type": "grid_500",
            "population_method": "spatial_join",
            "y_formula": "log_count",
            "model_type": "sem",
            "w_method": "knn_aic",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": False,
            "regime_type": "none",
            "regime_threshold": 0.3,
            "active_predictors": ["forests"],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": False,
            "run_lisa": False,
            "run_eta": False,
            "seed": 42,
        },
    },
    "RES-10": {
        "name": "Wplyw urbanizacji (Srodowiskowe)",
        "group": "Srodowiskowe",
        "config": {
            "geometry_type": "grid_500",
            "population_method": "spatial_join",
            "y_formula": "log_count",
            "model_type": "sem",
            "w_method": "knn_aic",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": False,
            "regime_type": "none",
            "regime_threshold": 0.3,
            "active_predictors": ["buildings", "roads", "barriers"],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": False,
            "run_lisa": False,
            "run_eta": False,
            "seed": 42,
        },
    },
    "RES-12": {
        "name": "Pelny model srodowiskowy (Srodowiskowe)",
        "group": "Srodowiskowe",
        "config": {
            "geometry_type": "grid_500",
            "population_method": "spatial_join",
            "y_formula": "log_count",
            "model_type": "auto",
            "w_method": "knn_aic",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": False,
            "regime_type": "none",
            "regime_threshold": 0.3,
            "active_predictors": [
                "forests",
                "buildings",
                "roads",
                "water",
                "barriers",
                "scrub",
                "parks",
                "meadows",
                "farmland",
                "allotments",
                "railway",
            ],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": True,
            "run_lisa": False,
            "run_eta": False,
            "seed": 42,
        },
    },
    # ─────────────────────────────────────────────────────────────
    # GRUPA D: KOREKTA / PERSPEKTYWY
    # ─────────────────────────────────────────────────────────────
    "RES-16": {
        "name": "Pustka populacyjna (Korekta)",
        "group": "Korekta",
        "config": {
            "geometry_type": "grid_500",
            "population_method": "spatial_join",
            "y_formula": "inv_pop",
            "model_type": "auto",
            "w_method": "knn_aic",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": False,
            "regime_type": "none",
            "regime_threshold": 0.3,
            "active_predictors": ["forests", "buildings"],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": True,
            "run_lisa": False,
            "run_eta": False,
            "seed": 42,
        },
    },
    "RES-17": {
        "name": "Obserwacje na mieszkanca (Korekta)",
        "group": "Korekta",
        "config": {
            "geometry_type": "grid_500",
            "population_method": "spatial_join",
            "y_formula": "count_pop",
            "model_type": "auto",
            "w_method": "knn_aic",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": True,
            "regime_type": "trinary",
            "regime_threshold_urban": 0.15,
            "regime_threshold": 0.3,
            "active_predictors": ["forests", "buildings", "roads", "water"],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": True,
            "run_lisa": False,
            "run_eta": False,
            "seed": 42,
        },
    },
    # ─────────────────────────────────────────────────────────────
    # GRUPA E: VORONOI
    # ─────────────────────────────────────────────────────────────
    "RES-22": {
        "name": "Voronoi podstawowy (Voronoi)",
        "group": "Voronoi",
        "config": {
            "geometry_type": "voronoi",
            "population_method": "points",
            "y_formula": "inv_pop",
            "model_type": "auto",
            "w_method": "knn_aic",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": False,
            "regime_type": "none",
            "regime_threshold": 0.3,
            "active_predictors": ["forests", "buildings", "water"],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": True,
            "run_lisa": False,
            "run_eta": False,
            "seed": 42,
        },
    },
    "RES-23": {
        "name": "Voronoi gestosc zaludnienia (Voronoi)",
        "group": "Voronoi",
        "config": {
            "geometry_type": "voronoi",
            "population_method": "points",
            "y_formula": "log_pop",
            "model_type": "auto",
            "w_method": "knn_aic",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": False,
            "regime_type": "none",
            "regime_threshold": 0.3,
            "active_predictors": ["forests", "buildings", "roads", "water"],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": True,
            "run_lisa": False,
            "run_eta": False,
            "seed": 42,
        },
    },
    "RES-24": {
        "name": "Voronoi tessW (Voronoi)",
        "group": "Voronoi",
        "config": {
            "geometry_type": "voronoi",
            "population_method": "points",
            "y_formula": "inv_pop",
            "model_type": "auto",
            "w_method": "tessw",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": False,
            "regime_type": "none",
            "regime_threshold": 0.3,
            "active_predictors": ["forests", "buildings", "roads", "water"],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": True,
            "run_lisa": False,
            "run_eta": True,
            "seed": 42,
        },
    },
    "RES-25": {
        "name": "Voronoi pelny + ETA (Voronoi)",
        "group": "Voronoi",
        "config": {
            "geometry_type": "voronoi",
            "population_method": "points",
            "y_formula": "inv_pop",
            "model_type": "auto",
            "w_method": "tessw",
            "k_range_min": 2,
            "k_range_max": 30,
            "use_regime_model": False,
            "regime_type": "none",
            "regime_threshold": 0.3,
            "active_predictors": [
                "forests",
                "buildings",
                "roads",
                "water",
                "barriers",
                "scrub",
            ],
            "vif_threshold": 5.0,
            "alpha": 0.05,
            "run_moran": True,
            "run_lm_tests": True,
            "run_lisa": True,
            "run_eta": True,
            "seed": 42,
        },
    },
}


class Command(BaseCommand):
    help = "Load research presets as database configurations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Count existing configs
        existing_count = ResearchConfig.objects.count()
        self.stdout.write(f"Istniejace konfiguracje: {existing_count}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN - zmiany nie zostana zapisane")
            )

        # Delete all existing configs
        if not dry_run:
            deleted_count, _ = ResearchConfig.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Usunieto {deleted_count} konfiguracji")
            )
        else:
            self.stdout.write(f"[DRY] Usunieto by {existing_count} konfiguracji")

        # Create new configs from presets
        created = 0
        first_preset_id = None

        for preset_id, preset in RESEARCH_PRESETS.items():
            name = preset["name"]
            config_data = preset["config"]

            if first_preset_id is None:
                first_preset_id = preset_id

            self.stdout.write(f"  {preset_id}: {name}")

            if not dry_run:
                ResearchConfig.objects.create(
                    name=name,
                    is_active=False,
                    geometry_type=config_data["geometry_type"],
                    population_method=config_data["population_method"],
                    y_formula=config_data["y_formula"],
                    model_type=config_data["model_type"],
                    w_method=config_data["w_method"],
                    k_range_min=config_data["k_range_min"],
                    k_range_max=config_data["k_range_max"],
                    use_regime_model=config_data["use_regime_model"],
                    regime_type=config_data["regime_type"],
                    regime_threshold=config_data["regime_threshold"],
                    regime_threshold_urban=config_data.get(
                        "regime_threshold_urban", 0.15
                    ),
                    active_predictors=config_data["active_predictors"],
                    vif_threshold=config_data["vif_threshold"],
                    alpha=config_data["alpha"],
                    run_moran=config_data["run_moran"],
                    run_lm_tests=config_data["run_lm_tests"],
                    run_lisa=config_data["run_lisa"],
                    run_eta=config_data["run_eta"],
                    seed=config_data["seed"],
                )
                created += 1

        # Activate the first (recommended) preset
        if not dry_run and first_preset_id:
            first_name = RESEARCH_PRESETS[first_preset_id]["name"]
            ResearchConfig.objects.filter(name=first_name).update(is_active=True)
            self.stdout.write(self.style.SUCCESS(f"\nAktywowano: {first_name}"))

        self.stdout.write(
            self.style.SUCCESS(f"\nUtworzono {len(RESEARCH_PRESETS)} konfiguracji")
        )
