import os
from django.conf import settings
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import RawMeasurement
from .serializers import RawMeasurementSerializer
from .services.pipeline import DataPipeline
from .services.telemetry import IngestionTelemetry

class MeasurementListAPIView(generics.ListAPIView):
    """
    Returns historical and real-time raw measurements for Mumbai stations.
    Supports filtering by ?station_id=OPENAQ_6927 or ?station=1, and ?limit=50.
    Safely clamps negative or excessive limits to [1, 500].
    """
    serializer_class = RawMeasurementSerializer

    def get_queryset(self):
        queryset = RawMeasurement.objects.select_related('station').all()

        station_id_code = self.request.query_params.get('station_id')
        station_pk = self.request.query_params.get('station')
        limit = self.request.query_params.get('limit')

        if station_id_code:
            queryset = queryset.filter(station__station_id=station_id_code)
        elif station_pk:
            queryset = queryset.filter(station_id=station_pk)

        try:
            limit_val = int(limit) if limit else 100
            limit_val = max(1, min(500, limit_val))
        except (ValueError, TypeError):
            limit_val = 100

        return queryset[:limit_val]

class TriggerIngestionAPIView(APIView):
    """
    Triggers an immediate ingestion pass for Mumbai stations.
    Protected by secret key check when INGESTION_SECRET_KEY is configured.
    """
    def post(self, request):
        required_secret = getattr(settings, 'INGESTION_SECRET_KEY', None) or os.getenv('INGESTION_SECRET_KEY')
        if not required_secret:
            return Response(
                {"error": "Server misconfiguration: INGESTION_SECRET_KEY is not defined."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        provided_secret = request.headers.get('X-Ingestion-Key') or request.data.get('secret_key')
        if not provided_secret or provided_secret != required_secret:
            return Response(
                {"error": "Unauthorized. A valid ingestion secret key is required via X-Ingestion-Key header or secret_key parameter."},
                status=status.HTTP_403_FORBIDDEN
            )

        days = request.data.get('days', 2)
        try:
            days_int = int(days)
            days_int = max(1, min(30, days_int))
        except (ValueError, TypeError):
            days_int = 2

        summary = DataPipeline.run_full_mumbai_pipeline(past_days=days_int)
        return Response({
            "message": "Ingestion pipeline completed successfully.",
            "summary": summary
        }, status=status.HTTP_200_OK)

class IngestionTelemetryAPIView(APIView):
    """
    GET /api/v1/ingestion/telemetry/
    Returns live operational status and ingestion telemetry.
    """
    def get(self, request):
        telemetry = IngestionTelemetry.get_full_system_telemetry()
        return Response(telemetry, status=status.HTTP_200_OK)
