from django.urls import path
from .views import system_health_check

urlpatterns = [
    path('health/', system_health_check, name='system-health-check'),
]
