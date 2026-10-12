from django.urls import path
from .views import ForecastAPIView, ModelMetricsAPIView

urlpatterns = [
    path('predict/', ForecastAPIView.as_view(), name='ml-predict'),
    path('models/', ModelMetricsAPIView.as_view(), name='ml-models'),
]
