from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import RawMeasurement
from .serializers import RawMeasurementSerializer
from .services.pipeline import DataPipeline

class MeasurementListAPIView(generics.ListAPIView):
    """
    Returns historical and real-time raw measurements for Mumbai stations.
    Supports filtering by ?station_id=MUM_BKC or ?station=1, and ?limit=50.
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
        except ValueError:
            limit_val = 100

        return queryset[:limit_val]

class TriggerIngestionAPIView(APIView):
    """
    Triggers an immediate ingestion pass for Mumbai stations.
    Useful for manual testing, mobile pull-to-refresh sync, and cron triggers.
    """
    def post(self, request):
        days = request.data.get('days', 2)
        try:
            days_int = int(days)
        except ValueError:
            days_int = 2

        summary = DataPipeline.run_full_mumbai_pipeline(past_days=days_int)
        return Response({
            "message": "Ingestion pipeline completed successfully.",
            "summary": summary
        }, status=status.HTTP_200_OK)
