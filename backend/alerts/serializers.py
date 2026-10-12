from rest_framework import serializers
from .models import AlertNotification, UserAlertSubscription

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
            'health_recommendations',
            'created_at',
            'is_active',
        ]


class UserAlertSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAlertSubscription
        fields = [
            'id',
            'email',
            'phone_number',
            'station',
            'threshold_aqi',
            'notify_sms',
            'notify_email',
            'is_active',
            'created_at',
        ]
