from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Avg, Max
from core.models import MonitoringStation
from aqi_engine.models import AQIRecord
from aqi_engine.serializers import AQIRecordSerializer
from aqi_engine.services.cpcb_calculator import CPCBCalculator

class LiveAQIListView(APIView):
    """
    Returns real-time latest AQI records for all active Mumbai stations,
    along with regional statistics (Mumbai City Average, Maximum AQI Hotspot, Cleanest Area).
    """
    def get(self, request):
        active_stations = MonitoringStation.objects.filter(is_active=True)
        station_records = []
        aqi_values = []

        for station in active_stations:
            latest_record = AQIRecord.objects.filter(station=station).select_related('station', 'raw_measurement').order_by('-recorded_at').first()
            if latest_record:
                serializer = AQIRecordSerializer(latest_record)
                station_records.append(serializer.data)
                if latest_record.overall_aqi is not None:
                    aqi_values.append(latest_record.overall_aqi)

        if aqi_values:
            city_avg_aqi = round(sum(aqi_values) / len(aqi_values), 1)
            category, color = CPCBCalculator.get_category_and_color(city_avg_aqi)
            worst_station = max(station_records, key=lambda x: x['overall_aqi'] or 0)
            cleanest_station = min(station_records, key=lambda x: x['overall_aqi'] or 999)
        else:
            city_avg_aqi = None
            category, color = ("No Data", "#9E9E9E")
            worst_station = None
            cleanest_station = None

        return Response({
            "region": "Greater Mumbai",
            "city_average_aqi": city_avg_aqi,
            "city_category": category,
            "city_color_hex": color,
            "monitored_stations_count": len(station_records),
            "worst_location": worst_station,
            "cleanest_location": cleanest_station,
            "stations": station_records
        }, status=status.HTTP_200_OK)

class StationAQIDetailView(APIView):
    """
    Returns latest full AQI breakdown for a specific station code (e.g. /api/v1/aqi/station/MUM_BKC/).
    """
    def get(self, request, station_id):
        station = MonitoringStation.objects.filter(station_id=station_id).first()
        if not station:
            return Response({"error": f"Station '{station_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        latest_record = AQIRecord.objects.filter(station=station).select_related('station', 'raw_measurement').order_by('-recorded_at').first()
        if not latest_record:
            return Response({"error": f"No AQI records available for station '{station_id}'."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AQIRecordSerializer(latest_record)
        return Response(serializer.data, status=status.HTTP_200_OK)

class HistoricalAQITrendView(APIView):
    """
    Returns time-series AQI and pollutant records for line chart plotting.
    Query parameters:
    - station_id (optional, default: MUM_BKC)
    - limit (optional, default: 48)
    """
    def get(self, request):
        station_id = request.query_params.get('station_id', 'MUM_BKC')
        limit = request.query_params.get('limit', 48)

        try:
            limit_int = int(limit)
        except ValueError:
            limit_int = 48

        station = MonitoringStation.objects.filter(station_id=station_id).first()
        if not station:
            return Response({"error": f"Station '{station_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        records = AQIRecord.objects.filter(station=station).select_related('station', 'raw_measurement').order_by('-recorded_at')[:limit_int]
        # Return in chronological order (oldest to newest) for chart plotting
        chronological_records = list(reversed(records))
        serializer = AQIRecordSerializer(chronological_records, many=True)

        return Response({
            "station_id": station.station_id,
            "station_name": station.name,
            "record_count": len(chronological_records),
            "history": serializer.data
        }, status=status.HTTP_200_OK)
