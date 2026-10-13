from rest_framework import serializers
from .models import AlertNotification, DeviceToken

class AlertNotificationSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True, default="Mumbai City")
    station_code = serializers.CharField(source='station.station_id', read_only=True, default="CITY")

    class Meta:
        model = AlertNotification
        fields = [
            'id',
            'station_code',
            'station_name',
            'title',
            'message',
            'severity',
            'aqi_value',
            'category',
            'prominent_pollutant',
            'is_forecast_alert',
            'forecast_horizon_hours',
            'health_recommendations',
            'created_at',
            'resolved_at',
            'is_active',
        ]


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = [
            'id',
            'token',
            'platform',
            'station',
            'is_active',
            'created_at',
            'last_seen_at',
        ]
