from django.urls import path
from .views import ActiveAlertsListView, AdvisoryRecommendationView, DeviceRegistrationView

app_name = 'alerts'

urlpatterns = [
    path('', ActiveAlertsListView.as_view(), name='active_alerts'),
    path('advisory/', AdvisoryRecommendationView.as_view(), name='advisory_recommendation'),
    path('device-token/', DeviceRegistrationView.as_view(), name='device_registration'),
    path('devices/', DeviceRegistrationView.as_view(), name='device_registration_alias'),
]
