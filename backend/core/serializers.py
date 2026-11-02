from rest_framework import serializers
from .models import MonitoringStation

class MonitoringStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoringStation
        fields = [
            'id',
            'station_id',
            'name',
            'latitude',
            'longitude',
            'zone_type',
            'city',
            'state',
            'is_active',
            'last_ground_observation_at',
            'consecutive_stale_cycles',
            'created_at'
        ]
