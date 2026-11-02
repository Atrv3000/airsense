from rest_framework import serializers
from django.utils import timezone
from .models import RawMeasurement, CleanMeasurement

def get_data_classification(source: str) -> str:
    if source in ('CPCB_OFFICIAL', 'WAQI_FEED', 'OPENAQ_MEASURED'):
        return "Ground measured"
    elif source == 'OPEN_METEO_MODELLED':
        return "Modelled"
    return "Modelled"

def get_provider_name(source: str) -> str:
    mapping = {
        'CPCB_OFFICIAL': 'Central Pollution Control Board (CPCB)',
        'WAQI_FEED': 'World Air Quality Index (WAQI)',
        'OPENAQ_MEASURED': 'OpenAQ Ground Sensor Network',
        'OPEN_METEO_MODELLED': 'Open-Meteo Atmospheric Model'
    }
    return mapping.get(source, 'Open-Meteo Atmospheric Model')

class RawMeasurementSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    station_id_code = serializers.CharField(source='station.station_id', read_only=True)
    data_classification = serializers.SerializerMethodField()
    provider = serializers.SerializerMethodField()
    is_stale = serializers.SerializerMethodField()
    freshness_hours = serializers.SerializerMethodField()

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
            'data_classification',
            'provider',
            'is_stale',
            'freshness_hours',
            'is_validated',
            'ingested_at'
        ]

    def get_data_classification(self, obj):
        return get_data_classification(obj.source)

    def get_provider_name(self, obj):
        return get_provider_name(obj.source)

    def get_provider(self, obj):
        return get_provider_name(obj.source)

    def get_freshness_hours(self, obj):
        if not obj.recorded_at:
            return None
        now = timezone.now()
        return round(max(0.0, (now - obj.recorded_at).total_seconds() / 3600.0), 1)

    def get_is_stale(self, obj):
        h = self.get_freshness_hours(obj)
        return h is None or h > 6.0


class CleanMeasurementSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    station_id_code = serializers.CharField(source='station.station_id', read_only=True)
    data_classification = serializers.SerializerMethodField()
    provider = serializers.SerializerMethodField()

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
            'data_classification',
            'provider',
            'is_imputed',
            'imputed_fields',
            'cleaned_at'
        ]

    def get_data_classification(self, obj):
        return get_data_classification(obj.source)

    def get_provider(self, obj):
        return get_provider_name(obj.source)
