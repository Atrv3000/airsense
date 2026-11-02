from django.urls import path
from .views import MeasurementListAPIView, TriggerIngestionAPIView, IngestionTelemetryAPIView

urlpatterns = [
    path('measurements/', MeasurementListAPIView.as_view(), name='measurement-list'),
    path('trigger/', TriggerIngestionAPIView.as_view(), name='trigger-ingestion'),
    path('telemetry/', IngestionTelemetryAPIView.as_view(), name='ingestion-telemetry'),
]
