from django.urls import path
from .views import (
    UnifiedMapLayersAPIView,
    HotspotsGeoJSONAPIView,
    FullGridGeoJSONAPIView,
    interactive_map_view
)

urlpatterns = [
    path('map-layers/', UnifiedMapLayersAPIView.as_view(), name='gis-map-layers'),
    path('hotspots/', HotspotsGeoJSONAPIView.as_view(), name='gis-hotspots'),
    path('grid/', FullGridGeoJSONAPIView.as_view(), name='gis-full-grid'),
    path('preview/', interactive_map_view, name='gis-map-preview'),
]
