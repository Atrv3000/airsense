from rest_framework import serializers
from .models import AQIRecord

class AQIRecordSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    station_id_code = serializers.CharField(source='station.station_id', read_only=True)
    latitude = serializers.FloatField(source='station.latitude', read_only=True)
    longitude = serializers.FloatField(source='station.longitude', read_only=True)

    # Raw concentrations from the linked raw measurement
    raw_pm25 = serializers.FloatField(source='raw_measurement.pm25', read_only=True)
    raw_pm10 = serializers.FloatField(source='raw_measurement.pm10', read_only=True)
    raw_no2 = serializers.FloatField(source='raw_measurement.no2', read_only=True)
    raw_so2 = serializers.FloatField(source='raw_measurement.so2', read_only=True)
    raw_co = serializers.FloatField(source='raw_measurement.co', read_only=True)
    raw_o3 = serializers.FloatField(source='raw_measurement.o3', read_only=True)
    temperature = serializers.FloatField(source='raw_measurement.temperature', read_only=True)
    humidity = serializers.FloatField(source='raw_measurement.humidity', read_only=True)
    wind_speed = serializers.FloatField(source='raw_measurement.wind_speed', read_only=True)
    source = serializers.CharField(source='raw_measurement.source', read_only=True, default='OPEN_METEO_MODELLED')

    class Meta:
        model = AQIRecord
        fields = [
            'id',
            'station_id_code',
            'station_name',
            'latitude',
            'longitude',
            'recorded_at',
            'source',
            'overall_aqi',
            'prominent_pollutant',
            'aqi_category',
            'color_hex',
            'valid_criteria_met',
            'is_instantaneous_fallback',
            'data_sufficiency_flags',
            # Sub-indices (Ip)
            'sub_index_pm25',
            'sub_index_pm10',
            'sub_index_no2',
            'sub_index_so2',
            'sub_index_co',
            'sub_index_o3',
            # Raw Concentrations (Cp) & Weather
            'raw_pm25',
            'raw_pm10',
            'raw_no2',
            'raw_so2',
            'raw_co',
            'raw_o3',
            'temperature',
            'humidity',
            'wind_speed'
        ]
