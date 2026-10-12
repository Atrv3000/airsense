from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.models import MonitoringStation
from aqi_engine.models import AQIRecord
from .services.hotspot_detector import HotspotDetector

def get_latest_station_readings():
    """
    Helper to fetch the latest AQI reading for each active Mumbai station.
    """
    active_stations = MonitoringStation.objects.filter(is_active=True)
    stations_data = []

    for station in active_stations:
        latest_aqi = AQIRecord.objects.filter(station=station).order_by('-recorded_at').first()
        if latest_aqi and latest_aqi.overall_aqi is not None:
            stations_data.append({
                'station_id': station.station_id,
                'name': station.name,
                'latitude': station.latitude,
                'longitude': station.longitude,
                'aqi': latest_aqi.overall_aqi
            })

    return stations_data

class HotspotsGeoJSONAPIView(APIView):
    """
    Returns detected air pollution hotspots across Mumbai as a standard GeoJSON FeatureCollection.
    Query parameters:
    - threshold: AQI threshold to qualify as hotspot (default: 200.0)
    - resolution: Spatial grid resolution, e.g. 25 for 25x25 (default: 25)
    """
    def get(self, request):
        threshold_param = request.query_params.get('threshold', 200.0)
        resolution_param = request.query_params.get('resolution', 25)

        try:
            threshold = float(threshold_param)
        except ValueError:
            threshold = 200.0

        try:
            resolution = int(resolution_param)
            resolution = max(10, min(50, resolution))  # Clamp between 10 and 50 for safety
        except ValueError:
            resolution = 25

        stations = get_latest_station_readings()
        if not stations:
            return Response({
                "type": "FeatureCollection",
                "metadata": {"error": "No station readings available to perform spatial interpolation."},
                "features": []
            }, status=status.HTTP_200_OK)

        geojson = HotspotDetector.detect_hotspots(
            known_stations=stations,
            threshold=threshold,
            resolution=resolution
        )
        return Response(geojson, status=status.HTTP_200_OK)

class FullGridGeoJSONAPIView(APIView):
    """
    Returns the complete interpolated regular grid across Greater Mumbai
    as a GeoJSON FeatureCollection (for full raster/heatmap rendering).
    """
    def get(self, request):
        resolution_param = request.query_params.get('resolution', 25)
        try:
            resolution = int(resolution_param)
            resolution = max(10, min(50, resolution))
        except ValueError:
            resolution = 25

        stations = get_latest_station_readings()
        if not stations:
            return Response({
                "type": "FeatureCollection",
                "features": []
            }, status=status.HTTP_200_OK)

        geojson = HotspotDetector.get_full_interpolated_grid_geojson(
            known_stations=stations,
            resolution=resolution
        )
        return Response(geojson, status=status.HTTP_200_OK)
