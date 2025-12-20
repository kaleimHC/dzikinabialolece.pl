"""
URL Configuration for Dziki na Białołęce project.
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import redis
import os


def health_check(request):
    """
    Health check endpoint for Docker/Kubernetes.
    Checks: PostGIS, Redis Cache, Redis Broker, PgBouncer connectivity.
    """
    status = {"status": "healthy", "checks": {}}

    # Check PostGIS
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT PostGIS_Version();")
            postgis_version = cursor.fetchone()[0]
            status["checks"]["postgis"] = {"status": "ok", "version": postgis_version}
    except Exception as e:
        status["checks"]["postgis"] = {"status": "error", "message": str(e)}
        status["status"] = "unhealthy"

    # Check Redis Cache
    try:
        cache.set("health_check", "ok", timeout=10)
        if cache.get("health_check") == "ok":
            status["checks"]["redis_cache"] = {"status": "ok"}
        else:
            raise Exception("Cache read failed")
    except Exception as e:
        status["checks"]["redis_cache"] = {"status": "error", "message": str(e)}
        # Cache failure is graceful degradation, not unhealthy
        status["checks"]["redis_cache"]["degraded"] = True

    # Check Redis Broker
    try:
        broker_url = os.environ.get(
            "CELERY_BROKER_URL", "redis://:redis_dev_password@redis-broker:6379/0"
        )
        # Parse password from URL
        r = redis.from_url(broker_url)
        r.ping()
        status["checks"]["redis_broker"] = {"status": "ok"}
    except Exception as e:
        status["checks"]["redis_broker"] = {"status": "error", "message": str(e)}
        status["status"] = "unhealthy"

    http_status = 200 if status["status"] == "healthy" else 503
    return JsonResponse(status, status=http_status)


urlpatterns = [
    # Admin - hidden behind secret URL for security
    path(os.environ.get("SECRET_ADMIN_URL", "secret") + "/admin/", admin.site.urls),
    # Health check (for Docker healthcheck)
    path("api/health/", health_check, name="health_check"),
    # API endpoints
    path("api/", include("sightings.urls")),
    path("api/analytics/", include("analytics.urls")),
    path("api/research/", include("analytics.urls_research")),
]
