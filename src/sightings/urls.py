"""
URL routing for Sightings app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SightingViewSet, GridCellViewSet

router = DefaultRouter()
router.register(r"sightings", SightingViewSet, basename="sighting")
router.register(r"grid", GridCellViewSet, basename="grid")

urlpatterns = [
    path("", include(router.urls)),
]
