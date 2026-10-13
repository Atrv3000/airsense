from rest_framework import serializers
from .models import RawMeasurement, CleanMeasurement

class RawMeasurementSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    station_id_code = serializers.CharField(source='station.station_id', read_only=True)

    class Meta:
        model = RawMeasurement
        fields = [
            'id',
            'station',
            'station_name',
            'station_id_code',
            'recorded_at',
            'pm25',
            'pm10',
            'no2',
            'so2',
            'co',
            'o3',
            'temperature',
            'humidity',
            'wind_speed',
            'wind_direction',
            'source',
            'is_validated',
            'ingested_at'
        ]


class CleanMeasurementSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    station_id_code = serializers.CharField(source='station.station_id', read_only=True)

    class Meta:
        model = CleanMeasurement
        fields = [
            'id',
            'station',
            'station_name',
            'station_id_code',
            'recorded_at',
            'pm25',
            'pm10',
            'no2',
            'so2',
            'co',
            'o3',
            'temperature',
            'humidity',
            'wind_speed',
            'wind_direction',
            'source',
            'is_imputed',
            'imputed_fields',
            'cleaned_at'
        ]
