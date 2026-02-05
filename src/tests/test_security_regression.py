"""
Security Regression Test Suite — Dziki na Białołęce

Verifies each security fix applied in recent commits:

  1. SQL injection blocked via grid_type / geometry_type allowlist validators
  2. WebSocket accepts anonymous connections [D-10] (portfolio, no login)
  3. Rate limit on POST /api/sightings/ is 100/hour
  4. NaN/Inf coordinates are rejected with HTTP 400
  5. Radius parameter capped at 50 km (no 500 error on huge values)
  6. All portfolio compute endpoints return non-401 for anonymous users [D-10]
  7. POST /api/sightings/ rejects coordinates outside Białołęka/Warsaw boundary

Run:
    pytest tests/test_security_regression.py -v
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory
from django.contrib.auth.models import User


# ---------------------------------------------------------------------------
# 1. SQL INJECTION — validator unit tests (no DB required)
# ---------------------------------------------------------------------------

from analytics.sql_injection_patch import (
    validate_grid_type,
    validate_geometry_type,
    validate_limit,
)


GRID_TYPE_SQL_PAYLOADS = [
    "'; DROP TABLE sightings_sighting;--",
    "voronoi UNION SELECT password,NULL,NULL FROM auth_user--",
    "voronoi; DROP TABLE auth_user; --",
    "voronoi\\nUNION SELECT pg_sleep(5)--",
    "(SELECT 1 FROM pg_sleep(5))",
    "1=1",
    "NULL",
    "voronoi%00",
    "../../etc/passwd",
]

GEOMETRY_TYPE_SQL_PAYLOADS = [
    "grid_500; DROP TABLE research_grid_500m;--",
    "grid_500 UNION SELECT * FROM auth_user--",
    "'; DELETE FROM sightings_sighting WHERE '1'='1",
    "grid_500\\nOR 1=1--",
    "(SELECT sleep(5))",
    "auth_user",
    "information_schema.tables",
    "grid_500%00",
    "NULL",
]


class TestSQLInjectionGridTypeAllowlist:
    """validate_grid_type() must only allow the four known values."""

    @pytest.mark.parametrize("payload", GRID_TYPE_SQL_PAYLOADS)
    def test_sql_payload_rejected(self, payload):
        with pytest.raises(ValueError, match="Invalid grid_type"):
            validate_grid_type(payload)

    def test_voronoi_accepted(self):
        assert validate_grid_type("voronoi") == "sightings_gridcell_voronoi"

    def test_square_accepted(self):
        assert validate_grid_type("square") == "sightings_gridcell_square"

    def test_research_accepted(self):
        assert validate_grid_type("research") == "sightings_gridcell_research"

    def test_grid_500_accepted(self):
        assert validate_grid_type("grid_500") == "sightings_gridcell_grid_500"

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError):
            validate_grid_type("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValueError):
            validate_grid_type("   ")

    def test_none_rejected(self):
        # str(None) == 'None' which is not in the allowlist
        with pytest.raises((ValueError, AttributeError)):
            validate_grid_type(None)

    def test_table_suffix_is_alphanumeric_or_underscore(self):
        """Returned table name must not contain characters that could escape SQL context."""
        for gt in ("voronoi", "square", "research", "grid_500"):
            table = validate_grid_type(gt)
            suffix = table[len("sightings_gridcell_"):]
            assert suffix.replace("_", "").isalnum(), (
                f"Unsafe character in table suffix: {suffix!r}"
            )


class TestSQLInjectionGeometryTypeAllowlist:
    """validate_geometry_type() covers the distributions endpoint."""

    @pytest.mark.parametrize("payload", GEOMETRY_TYPE_SQL_PAYLOADS)
    def test_sql_payload_rejected(self, payload):
        with pytest.raises(ValueError, match="Invalid geometry_type"):
            validate_geometry_type(payload)

    def test_grid_500_accepted(self):
        assert validate_geometry_type("grid_500") == "research_grid_500m"

    def test_voronoi_accepted(self):
        assert validate_geometry_type("voronoi") == "sightings_gridcell_voronoi"

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError):
            validate_geometry_type("")

    def test_none_rejected(self):
        with pytest.raises((ValueError, AttributeError)):
            validate_geometry_type(None)


class TestSQLInjectionValidateLimit:
    """validate_limit() must never produce a non-integer value usable in SQL."""

    def test_normal_integer_passes(self):
        assert validate_limit(50) == 50

    def test_string_integer_passes(self):
        assert validate_limit("200") == 200

    def test_oversized_value_clamped_to_max(self):
        result = validate_limit(999_999_999)
        assert result == 10_000

    def test_sql_injection_string_falls_back_to_default(self):
        result = validate_limit("100; DROP TABLE sightings_sighting;--")
        assert isinstance(result, int)
        assert result == 100

    def test_negative_value_falls_back_to_default(self):
        assert validate_limit(-99) == 100

    def test_zero_falls_back_to_default(self):
        assert validate_limit(0) == 100

    def test_union_select_in_limit_rejected(self):
        result = validate_limit("0 UNION SELECT password FROM auth_user--")
        assert isinstance(result, int)

    def test_float_string_truncated(self):
        # "3.14" cannot be cast via int() so it falls back to default
        result = validate_limit("3.14")
        assert isinstance(result, int)

    def test_custom_default_respected(self):
        assert validate_limit("bad", default=42, maximum=500) == 42

    def test_custom_maximum_respected(self):
        assert validate_limit(999, default=10, maximum=500) == 500


# ---------------------------------------------------------------------------
# 2. WEBSOCKET — [D-10] anonymous connections must be accepted (portfolio public)
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run a coroutine synchronously without pytest-asyncio dependency."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)


class TestWebSocketPublicAccess:
    """
    [D-10] PipelineProgressConsumer.connect() must accept anonymous users.
    The site has no login — rejecting anon with 4001 makes live progress unusable.
    Polling fallback exists but WebSocket should be the primary path.
    """

    def test_anonymous_user_can_connect(self):
        from analytics.consumers import PipelineProgressConsumer
        from django.contrib.auth.models import AnonymousUser

        async def _run():
            consumer = PipelineProgressConsumer()
            consumer.scope = {
                'user': AnonymousUser(),
                'url_route': {'kwargs': {'run_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'}},
            }
            consumer.close = AsyncMock()
            consumer.accept = AsyncMock()
            consumer.send = AsyncMock()
            consumer.channel_layer = AsyncMock()
            consumer.channel_layer.group_add = AsyncMock()
            consumer.channel_name = 'test_channel'

            await consumer.connect()

            consumer.accept.assert_called_once()
            consumer.close.assert_not_called()

        _run_async(_run())

    def test_any_user_can_connect(self):
        from analytics.consumers import PipelineProgressConsumer
        from django.contrib.auth.models import User

        async def _run():
            user = MagicMock(spec=User)
            user.is_authenticated = True

            consumer = PipelineProgressConsumer()
            consumer.scope = {
                'user': user,
                'url_route': {'kwargs': {'run_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'}},
            }
            consumer.close = AsyncMock()
            consumer.accept = AsyncMock()
            consumer.send = AsyncMock()
            consumer.channel_layer = AsyncMock()
            consumer.channel_layer.group_add = AsyncMock()
            consumer.channel_name = 'test_channel'

            await consumer.connect()

            consumer.accept.assert_called_once()
            consumer.close.assert_not_called()

        _run_async(_run())


# ---------------------------------------------------------------------------
# 3. RATE LIMIT — SightingThrottle is configured at 10/hour
# ---------------------------------------------------------------------------

class TestSightingThrottleConfiguration(TestCase):
    """
    SightingThrottle.rate must be '100/hour' (anti-bot, not a UX barrier).
    Changing the throttle class or the rate string requires deliberate review.
    """

    def test_throttle_rate_is_100_per_hour(self):
        from sightings.views import SightingThrottle
        assert SightingThrottle.rate == '100/hour', (
            f"Expected '100/hour', got {SightingThrottle.rate!r}"
        )

    def test_throttle_applied_only_to_create_action(self):
        """GET requests must NOT be throttled — only POST (create)."""
        from sightings.views import SightingViewSet
        from rest_framework.test import APIRequestFactory as RF

        factory = RF()
        view = SightingViewSet()

        # Simulate list action
        request = factory.get('/api/sightings/')
        view.request = request
        view.action = 'list'
        throttles = view.get_throttles()
        assert throttles == [], "GET /api/sightings/ should have no throttles"

        # Simulate create action
        view.action = 'create'
        throttles = view.get_throttles()
        from sightings.views import SightingThrottle
        assert any(isinstance(t, SightingThrottle) for t in throttles), (
            "POST /api/sightings/ (create) must use SightingThrottle"
        )

    def test_throttle_class_extends_anon_rate_throttle(self):
        """Must use AnonRateThrottle (IP-based) not UserRateThrottle."""
        from sightings.views import SightingThrottle
        from rest_framework.throttling import AnonRateThrottle
        assert issubclass(SightingThrottle, AnonRateThrottle)


# ---------------------------------------------------------------------------
# 4. NaN / Inf COORDINATE VALIDATION
# ---------------------------------------------------------------------------

class TestNaNInfCoordinateRejection(TestCase):
    """
    SightingCreateSerializer.validate_latitude/longitude must reject
    non-finite floats with HTTP 400, not crash with 500.
    """

    def _serialize(self, lat, lng):
        from sightings.serializers import SightingCreateSerializer
        s = SightingCreateSerializer(data={'latitude': lat, 'longitude': lng})
        return s.is_valid(), s.errors

    def test_nan_latitude_float_rejected(self):
        valid, errors = self._serialize(float('nan'), 21.0)
        assert not valid
