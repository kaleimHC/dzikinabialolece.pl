"""
DRF Serializers for Sightings app.
MASTER_SPEC v2.2 Architecture

Uses GeoFeatureModelSerializer for GeoJSON output.
"""

from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from django.contrib.gis.geos import Point
from .models import Sighting, GridCell, WarsawBoundary
import hashlib
import hmac
import math
import os


class SightingSerializer(GeoFeatureModelSerializer):
    """
    GeoJSON serializer for Sighting model.

    Output format:
    {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {...}
    }
    """

    class Meta:
        model = Sighting
        geo_field = "location"
        fields = [
            "id",
            "location",
            "observed_at",
            "status",
            "boar_count",
            "sighting_type",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "status", "ip_hash", "created_at", "updated_at"]


class SightingCreateSerializer(serializers.Serializer):
    """
    Serializer for creating new sightings via POST /api/sightings/.

    Validates:
    - Location is within Warsaw boundaries (ST_Contains)
    - observed_at is not in the future
    """

    latitude = serializers.FloatField(min_value=51.9, max_value=52.5)
    longitude = serializers.FloatField(min_value=20.5, max_value=21.5)
    observed_at = serializers.DateTimeField(required=False)
    boar_count = serializers.ChoiceField(
        choices=Sighting.BoarCount.choices, default=Sighting.BoarCount.SINGLE
    )
    description = serializers.CharField(
        max_length=1000, required=False, allow_blank=True
    )
    sighting_type = serializers.ChoiceField(
        choices=Sighting.SightingType.choices, default=Sighting.SightingType.ENCOUNTER
    )

    def validate_latitude(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("Latitude must be a finite number.")
        return value

    def validate_longitude(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("Longitude must be a finite number.")
        return value

    def validate(self, data):
        """Validate location is within Warsaw."""
        point = Point(data["longitude"], data["latitude"], srid=4326)

        if not WarsawBoundary.contains_point(point):
            raise serializers.ValidationError(
                {"location": "Lokalizacja musi być w granicach Warszawy."}
            )

        # Validate observed_at is not in the future
        from django.utils import timezone

        observed_at = data.get("observed_at", timezone.now())
        if observed_at > timezone.now():
            raise serializers.ValidationError(
                {"observed_at": "Data obserwacji nie może być w przyszłości."}
            )

        data["observed_at"] = observed_at
        return data

    def create(self, validated_data):
        """Create Sighting instance."""
        point = Point(
            validated_data["longitude"], validated_data["latitude"], srid=4326
        )

        # Hash IP for anti-spam (GDPR compliant)
        request = self.context.get("request")
        ip_hash = ""
        if request:
            ip = self._get_client_ip(request)
            ip_hash = self._hash_ip(ip)

        sighting = Sighting.objects.create(
            location=point,
            observed_at=validated_data["observed_at"],
            boar_count=validated_data["boar_count"],
            sighting_type=validated_data.get("sighting_type", "encounter"),
            description=validated_data.get("description", ""),
            ip_hash=ip_hash,
        )

        # Assign to grid cell (async would be better for production)
        self._assign_grid_cell(sighting)

        return sighting

    def _get_client_ip(self, request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def _hash_ip(self, ip: str) -> str:
        """Hash IP with HMAC-SHA256 for privacy."""
        secret = os.environ.get("IP_HASH_SECRET", "")
        if not secret:
            from django.conf import settings as _s

            if not _s.DEBUG:
                from django.core.exceptions import ImproperlyConfigured

                raise ImproperlyConfigured(
                    "IP_HASH_SECRET environment variable must be set in production."
                )
            secret = "dev-secret-change-in-production"
        return hmac.new(secret.encode(), ip.encode(), hashlib.sha256).hexdigest()

    def _assign_grid_cell(self, sighting: Sighting):
        """Assign sighting to appropriate grid cell."""
        try:
            grid_cell = GridCell.objects.filter(
                geometry__contains=sighting.location
            ).first()
            if grid_cell:
                sighting.grid_cell = grid_cell
                sighting.save(update_fields=["grid_cell"])
        except Exception:
            pass  # Graceful degradation


class GridCellSerializer(GeoFeatureModelSerializer):
    """GeoJSON serializer for GridCell aggregations."""

    class Meta:
        model = GridCell
        geo_field = "geometry"
        fields = [
            "grid_id",
            "geometry",
            "district",
            "sighting_count",
            "last_sighting_at",
        ]
