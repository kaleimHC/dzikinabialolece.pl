"""
API Views for Sightings app.
MASTER_SPEC v2.2 Architecture

Endpoints:
- POST /api/sightings/ - Create new sighting (rate limited)
- GET /api/sightings/ - List sightings (paginated, filterable)
- GET /api/sightings/{id}/ - Retrieve single sighting
- GET /api/grid/ - Grid cell aggregations
"""

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.throttling import AnonRateThrottle
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from django.utils import timezone
from datetime import timedelta

from .models import Sighting, GridCell
from .serializers import (
    SightingSerializer,
    SightingCreateSerializer,
    GridCellSerializer,
)


class SightingThrottle(AnonRateThrottle):
    """Custom throttle for sighting submissions: 1000/hour per IP (dev), 10/hour (prod)."""
    rate = '1000/hour'  # DEV: high limit for testing; TODO: reduce to 10/hour in production


class SightingCursorPagination(CursorPagination):
    """Cursor pagination for efficient large dataset handling."""
    page_size = 5000  # Increased to show all sightings on map
    ordering = '-observed_at'
    cursor_query_param = 'cursor'


class SightingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Sighting model.
    
    POST is rate-limited (10/hour per IP).
    GET supports spatial and temporal filters.
    """
    
    queryset = Sighting.objects.filter(status=Sighting.Status.VERIFIED)
    serializer_class = SightingSerializer
    pagination_class = SightingCursorPagination
    
    def get_throttles(self):
        """Apply throttle only to create action."""
        if self.action == 'create':
            return [SightingThrottle()]
        return []
    
    def get_serializer_class(self):
        """Use different serializer for create."""
        if self.action == 'create':
            return SightingCreateSerializer
        return SightingSerializer
    
    def get_queryset(self):
        """
        Filter queryset based on query parameters.
        
        Supported filters:
        - lat, lng, radius: Spatial filter (within radius km)
        - from_date, to_date: Temporal filter
        - district: Filter by district name
        """
        queryset = super().get_queryset()
        
        # Spatial filter: ?lat=52.2&lng=21.0&radius=5
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        radius = self.request.query_params.get('radius', 5)  # km
        
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
        
        # Temporal filter: ?from_date=2024-01-01&to_date=2024-12-31
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')
        
        if from_date:
            queryset = queryset.filter(observed_at__gte=from_date)
        if to_date:
            queryset = queryset.filter(observed_at__lte=to_date)
        
        # District filter: ?district=Białołęka
        district = self.request.query_params.get('district')
        if district:
            queryset = queryset.filter(grid_cell__district__icontains=district)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """
        Create new sighting.
        
        Rate limited: 10/hour per IP.
        Validates location is within Warsaw boundaries.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sighting = serializer.save()
        
        # Return created sighting in GeoJSON format
        output_serializer = SightingSerializer(sighting)
        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Get recent sightings (last 7 days).
        
        GET /api/sightings/recent/
        """
        week_ago = timezone.now() - timedelta(days=7)
        queryset = self.get_queryset().filter(observed_at__gte=week_ago)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get sighting statistics (cached).
        
        GET /api/sightings/stats/
        """
        from django.core.cache import cache
        
        cache_key = 'sighting_stats'
        stats = cache.get(cache_key)
        
        if stats is None:
            queryset = Sighting.objects.filter(status=Sighting.Status.VERIFIED)
            week_ago = timezone.now() - timedelta(days=7)
            month_ago = timezone.now() - timedelta(days=30)
            
            stats = {
                'total': queryset.count(),
                'last_7_days': queryset.filter(observed_at__gte=week_ago).count(),
                'last_30_days': queryset.filter(observed_at__gte=month_ago).count(),
                'pending_moderation': Sighting.objects.filter(
                    status=Sighting.Status.PENDING
                ).count(),
            }
            
            cache.set(cache_key, stats, timeout=300)  # 5 minutes
        
        return Response(stats)


class GridCellViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for GridCell aggregations.
    
    Read-only: grid cells are pre-populated.
    """
    
    queryset = GridCell.objects.filter(sighting_count__gt=0)
    serializer_class = GridCellSerializer
    pagination_class = None  # Return all cells (typically <1000)
    
    def get_queryset(self):
        """Filter by district if specified."""
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
