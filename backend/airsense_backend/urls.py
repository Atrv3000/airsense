"""
Root URL Configuration for AirSense Backend.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API v1 routes
    path('api/v1/', include('core.urls')),
    path('api/v1/ingestion/', include('ingestion.urls')),
    path('api/v1/aqi/', include('aqi_engine.urls')),
    path('api/v1/ml/', include('ml_engine.urls')),
    path('api/v1/gis/', include('spatial_gis.urls')),
]
