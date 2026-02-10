"""
Parameter configuration stub - name/description/is_active only.
Weights are computed directly in R scripts; this model is kept as a named-config hook.
"""

from django.db import models


class ParameterConfiguration(models.Model):
    """
    Named configuration profile. Singleton-active: only one can be active at a time.
    Ensemble weights live in R scripts (05_ensemble_prediction.R), not here.
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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_parameter_configuration"
        verbose_name = "Parameter Configuration"
        verbose_name_plural = "Parameter Configurations"
        ordering = ["-is_active", "-updated_at"]

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

    def apply_preset(self, preset_name: str) -> bool:
        from .models_config import PRESET_PROFILES

        if preset_name not in PRESET_PROFILES:
            raise ValueError(
                f"Unknown preset: {preset_name}. Valid: {list(PRESET_PROFILES.keys())}"
            )

        preset = PRESET_PROFILES[preset_name]
        self.name = f"{preset.get('name', preset_name)}"
        self.description = preset.get("description", "")
        return True

    @classmethod
    def create_from_preset(cls, preset_name: str, activate: bool = False):
        from .models_config import PRESET_PROFILES

        if preset_name not in PRESET_PROFILES:
            raise ValueError(f"Unknown preset: {preset_name}")

        preset = PRESET_PROFILES[preset_name]
        config = cls(
            name=f"{preset.get('name', preset_name)}",
            description=preset.get("description", ""),
            is_active=activate,
        )
        config.full_clean()
        config.save()
        return config


# PRESET PROFILES

PRESET_PROFILES = {
    "quick_preview": {
        "name": "Quick Preview",
        "description": "Szybki podgląd",
    },
    "conservative": {
        "name": "Conservative",
        "description": "Stabilne wyniki",
    },
    "aggressive": {
        "name": "Aggressive",
        "description": "Silne priory, wysoka persystencja",
    },
    "publication": {
        "name": "Publication Quality",
        "description": "Jakość publikacyjna",
    },
}


