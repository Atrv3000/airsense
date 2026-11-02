from django.urls import path
from .views import system_health_check, system_telemetry_check, StationListAPIView, StationDetailAPIView

urlpatterns = [
    path('health/', system_health_check, name='system-health-check'),
    path('health/telemetry/', system_telemetry_check, name='system-telemetry-check'),
    path('stations/', StationListAPIView.as_view(), name='station-list'),
    path('stations/<int:id>/', StationDetailAPIView.as_view(), name='station-detail'),
]
