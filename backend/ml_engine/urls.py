from django.urls import path
from .views import ForecastAPIView, ModelMetricsAPIView, ForecastVerificationAPIView

urlpatterns = [
    path('predict/', ForecastAPIView.as_view(), name='ml-predict'),
    path('models/', ModelMetricsAPIView.as_view(), name='ml-models'),
    path('metrics/', ModelMetricsAPIView.as_view(), name='ml-metrics'),
    path('verification/', ForecastVerificationAPIView.as_view(), name='ml-verification'),
]
