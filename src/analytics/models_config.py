"""
Bayesian Parameter Configuration.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError


class ParameterConfiguration(models.Model):
    """
    Central configuration for Bayesian layer parameters.

    Singleton-active: only one configuration can be active at a time.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Configuration profile name (e.g., 'production', 'quick_preview')",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(
        default=False, help_text="Only one configuration can be active"
    )

    bayesian_kappa = models.DecimalField(
        default=10.0,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(2.0), MaxValueValidator(50.0)],
        help_text="Prior concentration parameter kappa (2-50, default 10). Higher = stronger priors.",
    )

    persistence_rho_mean = models.DecimalField(
        default=0.82,
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(0.0), MaxValueValidator(0.99)],
        help_text="Expected persistence rho (0-0.99). From ARI via STS.",
    )

    diffusion_delta_mean = models.DecimalField(
        default=0.15,
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(0.0), MaxValueValidator(0.99)],
        help_text="Expected diffusion delta (0-0.99). From H_rel via ETA.",
    )

    mcmc_iterations = models.IntegerField(
        default=2000,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text="Total MCMC iterations per chain",
    )
    mcmc_warmup = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(50), MaxValueValidator(5000)],
        help_text="Warmup iterations (must be < iterations)",
    )
    mcmc_chains = models.IntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(8)],
        help_text="Number of MCMC chains (4 recommended for publication)",
    )
    mcmc_adapt_delta = models.DecimalField(
        default=0.95,
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(0.8), MaxValueValidator(0.999)],
        help_text="Stan adapt_delta parameter (higher = fewer divergences)",
    )
    mcmc_seed = models.IntegerField(
        default=42, help_text="Random seed for reproducibility"
    )

    bayesian_enabled = models.BooleanField(
        default=True, help_text="Enable Bayesian SSM layer"
    )

    # Ensemble weights — must sum to 1.0, validated in clean()

    # WAŻNE: Bayesian jest META-WARSTWĄ, nie składnikiem ensemble!
    # Wagi ensemble: RF + Spatial + ETA = 1.0 (0.30 + 0.40 + 0.30)
    # UWAGA: weight_gwr zachowane dla kompatybilności - używa spatial_risk (SAR/SEM)
    weight_rf = models.DecimalField(
        default=0.30,
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Random Forest weight in ensemble",
    )
    weight_gwr = models.DecimalField(
        default=0.40,
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Spatial model (SAR/SEM) weight in ensemble (legacy name: gwr)",
    )
    weight_eta = models.DecimalField(
        default=0.30,
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="ETA weight in ensemble",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_parameter_configuration"
        verbose_name = "Parameter Configuration"
        verbose_name_plural = "Parameter Configurations"
        ordering = ["-is_active", "-updated_at"]

    def clean(self):
        super().clean()

        # VALIDATION #1: rho + delta < 1.0 (stationarity)
        rho = float(self.persistence_rho_mean or 0)
        delta = float(self.diffusion_delta_mean or 0)
        if rho + delta >= 1.0:
            raise ValidationError(
                {
                    "persistence_rho_mean": (
                        f"rho + delta musi byc < 1.0 dla stacjonarnosci modelu! "
                        f"Obecne: {rho} + {delta} = {rho + delta}"
                    )
                }
            )

        # VALIDATION #2: weights sum to 1.0 (RF + GWR + ETA, Bayesian is META-layer)
        weights = [
            float(self.weight_rf or 0),
            float(self.weight_gwr or 0),
            float(self.weight_eta or 0),
        ]
        total = sum(weights)
        if not (0.99 <= total <= 1.01):
            raise ValidationError(
                {
                    "weight_rf": f"Wagi (RF+GWR+ETA) musza sumowac sie do 1.0! Obecna suma: {total:.4f}"
                }
            )

        # VALIDATION #3: warmup < iterations
        if self.mcmc_warmup and self.mcmc_iterations:
            if self.mcmc_warmup >= self.mcmc_iterations:
                raise ValidationError(
                    {"mcmc_warmup": "mcmc_warmup musi byc < mcmc_iterations!"}
                )

    def save(self, *args, **kwargs):
        if self.is_active:
            ParameterConfiguration.objects.filter(is_active=True).exclude(
                pk=self.pk
            ).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        status = "ACTIVE" if self.is_active else "inactive"
        return f"{self.name} ({status})"

    @classmethod
    def get_active(cls):
        """Return active config or None."""
        try:
            return cls.objects.get(is_active=True)
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_active_or_defaults(cls):
        """Return active config values as dict, or hardcoded defaults."""
        config = cls.get_active()
        if config:
            return {
                "kappa": float(config.bayesian_kappa),
                "rho_mean": float(config.persistence_rho_mean),
                "delta_mean": float(config.diffusion_delta_mean),
                "mcmc_iterations": config.mcmc_iterations,
                "mcmc_warmup": config.mcmc_warmup,
                "mcmc_chains": config.mcmc_chains,
                "mcmc_adapt_delta": float(config.mcmc_adapt_delta),
                "mcmc_seed": config.mcmc_seed,
                "bayesian_enabled": config.bayesian_enabled,
                "weights": {
                    "rf": float(config.weight_rf),
                    "gwr": float(config.weight_gwr),
                    "eta": float(config.weight_eta),
                },
            }
        else:
            return {
                "kappa": 10.0,
                "rho_mean": 0.82,
                "delta_mean": 0.15,
                "mcmc_iterations": 2000,
                "mcmc_warmup": 1000,
                "mcmc_chains": 4,
                "mcmc_adapt_delta": 0.95,
                "mcmc_seed": 42,
                "bayesian_enabled": True,
                "weights": {
                    "rf": 0.30,
                    "gwr": 0.40,
                    "eta": 0.30,
                },
            }

    def apply_preset(self, preset_name: str) -> bool:
        from decimal import Decimal
        from .models_config import PRESET_PROFILES

        if preset_name not in PRESET_PROFILES:
            raise ValueError(
                f"Unknown preset: {preset_name}. Valid: {list(PRESET_PROFILES.keys())}"
            )

        preset = PRESET_PROFILES[preset_name]

        def to_dec(val, places=3):
            return Decimal(str(val)).quantize(Decimal(10) ** -places)

        decimal_fields = [
            "bayesian_kappa",
            "persistence_rho_mean",
            "diffusion_delta_mean",
        ]
        int_fields = ["mcmc_iterations", "mcmc_warmup", "mcmc_chains"]

        for field in decimal_fields:
            if field in preset:
                places = 2 if field == "bayesian_kappa" else 3
                setattr(self, field, to_dec(preset[field], places))

        for field in int_fields:
            if field in preset:
                setattr(self, field, preset[field])

        self.name = f"{preset.get('name', preset_name)}"
        self.description = preset.get("description", "")

        return True

    @classmethod
    def create_from_preset(cls, preset_name: str, activate: bool = False):
        from decimal import Decimal
        from .models_config import PRESET_PROFILES

        if preset_name not in PRESET_PROFILES:
            raise ValueError(f"Unknown preset: {preset_name}")

        preset = PRESET_PROFILES[preset_name]

        def to_dec(val, places=3):
            return Decimal(str(val)).quantize(Decimal(10) ** -places)

        config = cls(
            name=f"{preset.get('name', preset_name)}",
            description=preset.get("description", ""),
            is_active=activate,
            bayesian_kappa=to_dec(preset.get("bayesian_kappa", 10), 2),
            persistence_rho_mean=to_dec(preset.get("persistence_rho_mean", 0.82)),
            diffusion_delta_mean=to_dec(preset.get("diffusion_delta_mean", 0.15)),
            mcmc_iterations=preset.get("mcmc_iterations", 2000),
            mcmc_warmup=preset.get("mcmc_warmup", 1000),
            mcmc_chains=preset.get("mcmc_chains", 4),
            mcmc_adapt_delta=to_dec(0.95),
            weight_rf=to_dec(0.30),
            weight_gwr=to_dec(0.40),
            weight_eta=to_dec(0.30),
        )
        config.full_clean()
        config.save()
        return config


# PRESET PROFILES

PRESET_PROFILES = {
    "quick_preview": {
        "name": "Quick Preview",
        "description": "Szybki podgląd (~5 min)",
        "bayesian_kappa": 5,
        "persistence_rho_mean": 0.60,
        "diffusion_delta_mean": 0.15,
        "mcmc_iterations": 500,
        "mcmc_warmup": 250,
        "mcmc_chains": 2,
    },
    "conservative": {
        "name": "Conservative",
        "description": "Stabilne wyniki (~30 min)",
        "bayesian_kappa": 5,
        "persistence_rho_mean": 0.50,
        "diffusion_delta_mean": 0.15,
        "mcmc_iterations": 2000,
        "mcmc_warmup": 1000,
        "mcmc_chains": 4,
    },
    "aggressive": {
        "name": "Aggressive",
        "description": "Silne priory, wysoka persystencja (~30 min)",
        "bayesian_kappa": 25,
        "persistence_rho_mean": 0.82,
        "diffusion_delta_mean": 0.15,
        "mcmc_iterations": 2000,
        "mcmc_warmup": 1000,
        "mcmc_chains": 4,
    },
    "publication": {
        "name": "Publication Quality",
        "description": "Jakość publikacyjna (~60 min)",
        "bayesian_kappa": 10,
        "persistence_rho_mean": 0.82,
        "diffusion_delta_mean": 0.15,
        "mcmc_iterations": 4000,
        "mcmc_warmup": 2000,
        "mcmc_chains": 4,
    },
}


# N MINIMUM REQUIREMENTS

N_MINIMUM_REQUIREMENTS = {
    "eta": {
        "min": 3,
        "action": "error",
        "message": "ETA wymaga minimum 3 obserwacji",
    },
    "gwr": {  # legacy key - now SAR/SEM
        "min": 100,
        "action": "error",
        "message": "Spatial model (SAR/SEM) wymaga minimum 100 obserwacji",
    },
    "bayesian": {
        "warn": 50,
        "recommended": 200,
        "action": "warn",
        "message": "Bayesian SSM: N>=50 (ostrzezenie), N>=200 (zalecane)",
    },
}


def check_n_minimum(n_obs: int, model_type: str) -> dict:
    """Check if sample size meets minimum requirements for ETA/GWR/Bayesian models."""
    if model_type not in N_MINIMUM_REQUIREMENTS:
        return {"ok": True, "warning": None, "error": None, "message": None}

    req = N_MINIMUM_REQUIREMENTS[model_type]

    if "min" in req and n_obs < req["min"]:
        return {
            "ok": False,
            "warning": None,
            "error": True,
            "message": f"{req['message']}. N={n_obs} < {req['min']}",
        }

    if "warn" in req:
        if n_obs < req["warn"]:
            return {
                "ok": False,
                "warning": True,
                "error": True,
                "message": f"{req['message']}. N={n_obs} < {req['warn']}",
            }
        if n_obs < req.get("recommended", req["warn"]):
            return {
                "ok": True,
                "warning": True,
                "error": None,
                "message": f"N={n_obs} poniżej zalecanego {req['recommended']}. {req['message']}",
            }

    return {"ok": True, "warning": None, "error": None, "message": None}
