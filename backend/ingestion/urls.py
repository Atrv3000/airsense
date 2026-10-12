from django.urls import path
from .views import MeasurementListAPIView, TriggerIngestionAPIView

urlpatterns = [
    path('measurements/', MeasurementListAPIView.as_view(), name='measurement-list'),
    path('trigger/', TriggerIngestionAPIView.as_view(), name='trigger-ingestion'),
]
