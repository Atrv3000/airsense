from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import connection
from datetime import datetime
from .models import MonitoringStation
from .serializers import MonitoringStationSerializer
from ingestion.services.telemetry import IngestionTelemetry

@api_view(['GET'])
def system_health_check(request):
    """
    Health check endpoint to verify backend status, PostgreSQL database connectivity,
    server time, and complete operational provider telemetry.
    Preserves exact backward-compatible keys ('status', 'database', 'project', 'timestamp', 'version').
    """
    db_status = "Disconnected"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            if row and row[0] == 1:
                db_status = "Connected (PostgreSQL)"
    except Exception as e:
        db_status = f"Database Error: {str(e)}"

    telemetry = IngestionTelemetry.get_full_system_telemetry()

    return Response({
        "status": "online",
        "project": "AirSense - Mumbai Air Quality Monitoring & Hotspot Prediction",
        "database": db_status,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "telemetry": telemetry
    })

@api_view(['GET'])
def system_telemetry_check(request):
    """
    Dedicated operational telemetry endpoint for system health monitoring dashboards.
    Reports OpenAQ, Open-Meteo, and WAQI/CPCB live connectivity, observation freshness,
    failed request counters, and ingestion cycle durations.
    """
    telemetry = IngestionTelemetry.get_full_system_telemetry()
    return Response(telemetry, status=status.HTTP_200_OK)

class StationListAPIView(generics.ListAPIView):
    """
    Returns a list of all ambient air monitoring stations in Mumbai.
    Supports ?active=true filter.
    """
    serializer_class = MonitoringStationSerializer

    def get_queryset(self):
        queryset = MonitoringStation.objects.all()
        active_filter = self.request.query_params.get('active')
        if active_filter is not None:
            is_active = active_filter.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(is_active=is_active)
        return queryset

class StationDetailAPIView(generics.RetrieveAPIView):
    """
    Returns details for a specific monitoring station by ID.
    """
    queryset = MonitoringStation.objects.all()
    serializer_class = MonitoringStationSerializer
    lookup_field = 'id'
