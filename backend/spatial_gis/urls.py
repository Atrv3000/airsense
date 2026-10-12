from django.urls import path
from .views import HotspotsGeoJSONAPIView, FullGridGeoJSONAPIView

urlpatterns = [
    path('hotspots/', HotspotsGeoJSONAPIView.as_view(), name='gis-hotspots'),
    path('grid/', FullGridGeoJSONAPIView.as_view(), name='gis-full-grid'),
]
