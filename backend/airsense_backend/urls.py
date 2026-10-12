"""
Root URL Configuration for AirSense Backend.
"""
from django.contrib import admin
from django.urls import path, include
from spatial_gis.views import interactive_map_view

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Web GIS Interactive Preview (Viva Demo & Testing)
    path('map/', interactive_map_view, name='web-mumbai-map'),

    # API v1 routes
    path('api/v1/', include('core.urls')),
    path('api/v1/ingestion/', include('ingestion.urls')),
    path('api/v1/aqi/', include('aqi_engine.urls')),
    path('api/v1/ml/', include('ml_engine.urls')),
    path('api/v1/gis/', include('spatial_gis.urls')),
]
