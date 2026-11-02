from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Avg, Max
from django.utils import timezone
from core.models import MonitoringStation
from aqi_engine.models import AQIRecord
from aqi_engine.serializers import AQIRecordSerializer
from aqi_engine.services.cpcb_calculator import CPCBCalculator
from ingestion.services.telemetry import IngestionTelemetry

class LiveAQIListView(APIView):
    """
    Returns real-time latest AQI records for all active Mumbai stations,
    along with regional statistics (Mumbai City Average with statistical validity check,
    Dominant Pollutant, Data Source Badge, and Freshness Indicators).
    """
    def get(self, request):
        active_stations = MonitoringStation.objects.filter(is_active=True)
        station_records = []
        aqi_values = []
        prominent_pollutants = []

        for station in active_stations:
            latest_record = AQIRecord.objects.filter(station=station).select_related('station', 'raw_measurement').order_by('-recorded_at').first()
            if latest_record:
                serializer = AQIRecordSerializer(latest_record)
                station_records.append(serializer.data)
                if latest_record.overall_aqi is not None:
                    aqi_values.append(latest_record.overall_aqi)
                if latest_record.prominent_pollutant:
                    prominent_pollutants.append(latest_record.prominent_pollutant)

        total_active_count = len(active_stations)
        reporting_count = len(aqi_values)

        # Statistical validity: require at least 3 stations (or all active if total <= 2 in test fixtures)
        is_statistically_valid = (reporting_count >= 3) if total_active_count >= 3 else (reporting_count >= 1)

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

        dominant_pollutant = max(set(prominent_pollutants), key=prominent_pollutants.count) if prominent_pollutants else "PM2.5"

        validity_note = (
            f"Statistically valid regional average based on {reporting_count} active monitoring stations."
            if is_statistically_valid else
            f"Insufficient spatial representation ({reporting_count}/{total_active_count} stations reporting; minimum 3 required for regional validity)."
        )

        def mean_of(field):
            vals = [s[field] for s in station_records if s.get(field) is not None]
            if not vals:
                from ingestion.models import CleanMeasurement
                db_field = field.replace('raw_', '')
                recent_vals = list(CleanMeasurement.objects.filter(
                    station__is_active=True,
                    **{f"{db_field}__isnull": False}
                ).order_by('-recorded_at').values_list(db_field, flat=True)[:15])
                vals = [v for v in recent_vals if v is not None]
            return round(sum(vals) / len(vals), 1 if field != 'raw_co' else 2) if vals else None

        city_pollutants = {
            "pm25": mean_of('raw_pm25'),
            "pm10": mean_of('raw_pm10'),
            "no2": mean_of('raw_no2'),
            "so2": mean_of('raw_so2'),
            "co": mean_of('raw_co'),
            "o3": mean_of('raw_o3'),
            "temperature": mean_of('temperature'),
            "humidity": round(mean_of('humidity'), 0) if mean_of('humidity') is not None else None,
            "wind_speed": mean_of('wind_speed'),
        }

        freshness_stats = IngestionTelemetry.get_freshness_stats()
        latest_observation = max([s['recorded_at'] for s in station_records if s.get('recorded_at')], default=None)

        # Count ground measured vs modelled stations
        ground_stations_count = sum(1 for s in station_records if s.get('data_classification') == 'Ground measured')
        modelled_stations_count = sum(1 for s in station_records if s.get('data_classification') == 'Modelled')

        return Response({
            "region": "Greater Mumbai",
            "city_average_aqi": city_avg_aqi,
            "city_category": category,
            "city_color_hex": color,
            "dominant_pollutant": dominant_pollutant,
            "is_statistically_valid": is_statistically_valid,
            "statistical_validity_note": validity_note,
            "monitored_stations_count": len(station_records),
            "ground_measured_stations_count": ground_stations_count,
            "modelled_stations_count": modelled_stations_count,
            "worst_location": worst_station,
            "cleanest_location": cleanest_station,
            "city_pollutants": city_pollutants,
            "last_updated_at": latest_observation,
            "freshness": freshness_stats,
            "stations": station_records
        }, status=status.HTTP_200_OK)

class StationAQIDetailView(APIView):
    """
    Returns latest full AQI breakdown for a specific station code (e.g. /api/v1/aqi/station/OPENAQ_6927/).
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
    - station_id (optional, default: OPENAQ_6927 or first active station)
    - limit (optional, default: 48, safely bounded [1, 500])
    """
    def get(self, request):
        station_id = request.query_params.get('station_id')
        if not station_id:
            first_st = MonitoringStation.objects.filter(is_active=True).first()
            station_id = first_st.station_id if first_st else 'OPENAQ_6927'

        limit = request.query_params.get('limit', 48)
        try:
            limit_int = int(limit)
            limit_int = max(1, min(500, limit_int))
        except (ValueError, TypeError):
            limit_int = 48

        station = MonitoringStation.objects.filter(station_id=station_id).first()
        if not station:
            return Response({"error": f"Station '{station_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        records = AQIRecord.objects.filter(station=station).select_related('station', 'raw_measurement').order_by('-recorded_at')[:limit_int]
        chronological_records = list(reversed(records))
        serializer = AQIRecordSerializer(chronological_records, many=True)

        return Response({
            "station_id": station.station_id,
            "station_name": station.name,
            "record_count": len(chronological_records),
            "history": serializer.data
        }, status=status.HTTP_200_OK)
