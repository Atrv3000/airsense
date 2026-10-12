from django.urls import path
from .views import ActiveAlertsListView, AdvisoryRecommendationView, UserSubscriptionView

app_name = 'alerts'

urlpatterns = [
    path('', ActiveAlertsListView.as_view(), name='active_alerts'),
    path('advisory/', AdvisoryRecommendationView.as_view(), name='advisory_recommendation'),
    path('subscribe/', UserSubscriptionView.as_view(), name='user_subscription'),
]
