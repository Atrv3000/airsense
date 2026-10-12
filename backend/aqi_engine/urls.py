from django.urls import path
from .views import LiveAQIListView, StationAQIDetailView, HistoricalAQITrendView

urlpatterns = [
    path('live/', LiveAQIListView.as_view(), name='live-aqi'),
    path('station/<str:station_id>/', StationAQIDetailView.as_view(), name='station-aqi-detail'),
    path('historical/', HistoricalAQITrendView.as_view(), name='historical-aqi-trend'),
]
