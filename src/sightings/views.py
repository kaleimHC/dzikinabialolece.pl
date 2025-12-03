"""
API Views for Sightings app.
MASTER_SPEC v2.2 Architecture

Endpoints:
- GET /api/sightings/ - List sightings (paginated, filterable)
- GET /api/sightings/{id}/ - Retrieve single sighting
"""

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from django.utils import timezone
from datetime import timedelta

from .models import Sighting, GridCell
from .serializers import SightingSerializer, GridCellSerializer


class SightingCursorPagination(CursorPagination):
    """Cursor pagination for efficient large dataset handling."""
    page_size = 5000
    ordering = '-observed_at'
    cursor_query_param = 'cursor'


class SightingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Sighting model — list and retrieve only.

    GET supports spatial and temporal filters.
    """

    queryset = Sighting.objects.filter(status=Sighting.Status.VERIFIED)
    serializer_class = SightingSerializer
    pagination_class = SightingCursorPagination

    def get_queryset(self):
        queryset = super().get_queryset()

        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        radius = self.request.query_params.get('radius', 5)

        if lat and lng:
            try:
                point = Point(float(lng), float(lat), srid=4326)
                queryset = queryset.filter(
                    location__distance_lte=(point, D(km=float(radius)))
                ).annotate(
                    distance=Distance('location', point)
                ).order_by('distance')
            except (ValueError, TypeError):
                pass

        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')

        if from_date:
            queryset = queryset.filter(observed_at__gte=from_date)
        if to_date:
            queryset = queryset.filter(observed_at__lte=to_date)

        district = self.request.query_params.get('district')
        if district:
            queryset = queryset.filter(grid_cell__district__icontains=district)

        return queryset

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent sightings (last 7 days)."""
        week_ago = timezone.now() - timedelta(days=7)
        queryset = self.get_queryset().filter(observed_at__gte=week_ago)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class GridCellViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for GridCell aggregations — read-only."""

    queryset = GridCell.objects.filter(sighting_count__gt=0)
    serializer_class = GridCellSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        district = self.request.query_params.get('district')
        if district:
            queryset = queryset.filter(district__icontains=district)
        min_count = self.request.query_params.get('min_count', 1)
        try:
            queryset = queryset.filter(sighting_count__gte=int(min_count))
        except ValueError:
            pass
        return queryset
