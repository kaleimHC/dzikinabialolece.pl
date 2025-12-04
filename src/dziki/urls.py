"""
URL Configuration for Dziki na Białołęce project.
MASTER_SPEC v2.2 Architecture
"""

from django.urls import path, include
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import redis
import os


def health_check(request):
    """Health check endpoint for Docker/Kubernetes."""
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('api/health/', health_check, name='health_check'),
    path('api/', include('sightings.urls')),
    path('api/analytics/', include('analytics.urls')),
]
